"""Inference/acquisition algebra checks on synthetic paid-data fixtures."""
import ast
from copy import deepcopy
from pathlib import Path
import time
import unittest

import numpy as np
from scipy.linalg import cho_factor, cho_solve
from scipy.special import logsumexp

from budgeted_science.resource_planning.emulator import (
    Calibration, GPSettings, kernel, stable_weights, uncertainty,
)
from budgeted_science.resource_planning.policies import make_design, rank_actions, next_candidates


BOUNDS = np.array([[.8, 1.2], [.06, .1], [1.1, 1.7]])
TIMES = np.arange(.5, 8.01, .5)
INITIAL = np.array([10., 5.])


def fixture():
    simulations = []
    points = [[1., .08, 1.4], [.83, .095, 1.3], [1.16, .07, 1.6], [.95, .085, 1.15]]
    for fidelity, theta in [("low", p) for p in points] + [("high", points[0])]:
        # Smooth synthetic fixtures, not the private predator-prey equations.
        z = (np.array(theta) - BOUNDS[:, 0]) / np.diff(BOUNDS).ravel()
        v = np.array([1 + .2*z[0]*np.sin(TIMES) + .1*z[1]*TIMES,
                      1 + .2*z[2]*np.cos(TIMES) - .03*z[1]*TIMES]).T
        if fidelity == "low":
            v += .02 * np.sin(TIMES)[:, None]
        simulations.append({"status": "success", "theta": theta, "fidelity": fidelity,
                            "times": TIMES.tolist(), "values": (v * INITIAL).tolist()})
    obs = [{"variable": "x", "time": 1., "value": 11.1},
           {"variable": "y", "time": 1., "value": 5.1}]
    return simulations, obs


class TestKernel(unittest.TestCase):
    def test_settings_validate_counts(self):
        for kwargs in ({'particles':0}, {'particles':31}, {'fantasies':0}, {'global_candidates':-1},
                       {'posterior_candidates':3000}, {'time_length':float('nan')}):
            with self.assertRaises(ValueError): GPSettings(**kwargs)
    def test_kernel_derivatives(self):
        a = np.array([[.2,.3,.4], [.9,.7,.1], [.1,.4,.8]])
        f = np.array([0,1,1])
        hp = np.log([.4,.6,.8,.3,.5,.7,1.,.3])
        _, gradients = kernel(a,f,a,f,hp,True)
        for i, gradient in enumerate(gradients):
            offset = np.zeros(8); offset[i] = 1e-6
            finite = (kernel(a,f,a,f,hp+offset) - kernel(a,f,a,f,hp-offset)) / 2e-6
            np.testing.assert_allclose(gradient, finite, rtol=1e-5, atol=1e-7)

    def test_low_high_relationship(self):
        a = np.array([[.2,.3,.4]])
        hp = np.log([.5]*6+[1.,.25])
        ll = kernel(a,[0],a,[0],hp)
        lh = kernel(a,[0],a,[1],hp)
        hh = kernel(a,[1],a,[1],hp)
        np.testing.assert_equal(ll,lh)
        self.assertGreater(hh[0,0],ll[0,0])


class TestCalibration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.simulations, cls.observations = fixture()
        cls.settings = GPSettings(particles=32, fantasies=2, max_fit_iterations=3)
        cls.cal = Calibration(cls.simulations,cls.observations,BOUNDS,INITIAL,TIMES,settings=cls.settings)

    def test_finite_estimate_and_correlated_times(self):
        c=self.cal
        self.assertAlmostEqual(c.weights.sum(),1.)
        estimate=np.array(c.estimate())
        self.assertTrue(np.all((estimate>=BOUNDS[:,0]) & (estimate<=BOUNDS[:,1])))
        self.assertGreater(c.temporal[0,1],.1)
        self.assertTrue(np.isfinite(c.current_uncertainty))

    def test_log_likelihood_against_dense(self):
        c=self.cal
        for particle in [0,7,15]:
            expected=0
            for j,obs in enumerate(c.obs):
                ids=[o[0] for o in obs]
                residual=np.array([o[1] for o in obs])-c.means[j][particle,ids]
                cov=c.variances[j][particle]*c.temporal[np.ix_(ids,ids)]+np.eye(len(ids))*c.settings.likelihood_jitter
                expected-=.5*(np.linalg.slogdet(cov)[1]+residual@np.linalg.solve(cov,residual))
            self.assertAlmostEqual(expected,c.log_likelihood[particle],places=9)

    def test_target_conditional_matches_dense(self):
        c=self.cal
        mean,cov=c.condition_target(0,[4,8])
        for p in [0,3]:
            ids=[4,8,1]
            full=c.variances[0][p]*c.temporal[np.ix_(ids,ids)]
            vv=full[2,2]+c.settings.likelihood_jitter
            residual=c.obs[0][0][1]-c.means[0][p,1]
            expectedmean=c.means[0][p,[4,8]]+full[:2,2]/vv*residual
            expectedcov=full[:2,:2]-np.outer(full[:2,2],full[2,:2])/vv
            np.testing.assert_allclose(mean[p],expectedmean,atol=1e-10)
            np.testing.assert_allclose(cov[p],expectedcov,atol=1e-10)

    def test_full_trajectory_conditioning_matches_augmented_gp(self):
        c=self.cal; gp=c.channels[0]
        location=np.array([[.4,.6,.5]]); fidelity=np.ones(1)
        am,av=gp.predict(location,fidelity)
        action_variance=av[0]+c.settings.run_jitter
        outcome=am[0]+np.linspace(-.02,.02,len(TIMES))
        cross=gp.cross(c.unit_particles,np.ones(len(c.particles)),location,fidelity)[:,0]
        fastmean=c.means[0]+cross[:,None]/action_variance*(outcome-am[0])
        fastvar=c.variances[0]-cross**2/action_variance
        theta=np.vstack((gp.theta,location)); flags=np.r_[gp.fidelities,1]
        training=kernel(theta,flags,theta,flags,gp.hp)+np.eye(len(theta))*c.settings.run_jitter
        between=kernel(c.unit_particles,np.ones(len(c.particles)),theta,flags,gp.hp)
        factor=cho_factor(training,lower=True)
        expected=between@cho_solve(factor,np.vstack((gp.values,outcome)))
        prior=np.exp(2*gp.hp[6])+np.exp(2*gp.hp[7])
        expectedvar=prior-np.sum(between*cho_solve(factor,between.T).T,axis=1)
        np.testing.assert_allclose(fastmean,expected,atol=2e-7)
        np.testing.assert_allclose(fastvar,expectedvar,atol=2e-7)

    def test_hypothetical_updates_are_finite_repeatable_and_immutable(self):
        c=self.cal
        before=c.weights.copy(); hp=[g.hp.copy() for g in c.channels]
        rng=np.random.default_rng(19); draws=rng.choice(32,2,p=c.weights)
        normals=rng.normal(size=(2,2,len(TIMES)))
        a=c.simulation_gain([1.1,.09,1.5],"high",draws,normals)
        b=c.simulation_gain([1.1,.09,1.5],"high",draws,normals)
        d=c.observation_gain(1,10,draws,normals)
        self.assertEqual(a,b); self.assertTrue(np.isfinite([a,d]).all())
        np.testing.assert_equal(c.weights,before)
        for g,old in zip(c.channels,hp): np.testing.assert_equal(g.hp,old)

    def test_observation_gain_direct_reweighting(self):
        c=self.cal; draws=np.array([2,8]); normals=np.zeros((2,2,len(TIMES)))
        mean,cov=c.condition_target(1,[10]); variance=cov[:,0,0]+c.settings.likelihood_jitter
        outcomes=mean[draws,0]
        ll=c.log_likelihood[None,:]-.5*(np.log(variance)+(outcomes[:,None]-mean[:,0])**2/variance)
        expected=c.current_uncertainty-uncertainty(stable_weights(ll),c.log_particles).mean()
        self.assertAlmostEqual(c.observation_gain(1,10,draws,normals),expected,places=10)

    def test_deadline_stops_analysis(self):
        with self.assertRaises(TimeoutError):
            Calibration(self.simulations,self.observations,BOUNDS,INITIAL,TIMES,
                        settings=self.settings,deadline=time.monotonic()-1)

    def test_no_solver_dependency(self):
        import budgeted_science.resource_planning.emulator as module
        import budgeted_science.resource_planning.policies as policies
        for source in [module,policies]:
            tree=ast.parse(Path(source.__file__).read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node,ast.ImportFrom):
                    self.assertNotIn("environment",node.module or "")
                if isinstance(node,ast.Attribute):
                    self.assertNotIn(node.attr,["solve_ivp","_target","evaluate"])

    def test_misordered_trajectory_times_rejected(self):
        data=deepcopy(self.simulations)
        for item in data:
            item['times']=item['times'][::-1]; item['values']=item['values'][::-1]
        with self.assertRaises(ValueError):
            Calibration(data,self.observations,BOUNDS,INITIAL,TIMES,settings=self.settings)

    def test_candidate_counts_zero_and_above_eight(self):
        config={'costs':{'low':1,'high':8,'measurement':12},'working_times':TIMES.tolist()}
        evidence={'simulations':self.simulations,'observations':self.observations}
        c=self.cal; original=c.settings
        try:
            c.settings=GPSettings(particles=32,global_candidates=0,posterior_candidates=0)
            self.assertEqual(next_candidates(c,evidence,config,1,0,0),[])
            c.settings=GPSettings(particles=32,global_candidates=16,posterior_candidates=0)
            self.assertEqual(len(next_candidates(c,evidence,config,1,0,0)),16)
        finally:
            c.settings=original


class TestPolicies(unittest.TestCase):
    def test_fixed_design_seed_and_price(self):
        a,b=make_design(0,BOUNDS,TIMES)
        aa,bb=make_design(0,BOUNDS,TIMES)
        self.assertEqual((a,b),(aa,bb)); self.assertEqual(len(a),5)
        allactions=a+b
        cost=sum(12 if x['kind']=='observation' else (1 if x['fidelity']=='low' else 8) for x in allactions)
        self.assertEqual(cost,40)
        self.assertEqual(sum(x['kind']=='observation' for x in allactions),1)
        self.assertNotEqual(make_design(1,BOUNDS,TIMES),(a,b))

    def test_adaptive_ranking_changes_with_evidence_and_uses_cost(self):
        class Controlled:
            settings=GPSettings(fantasies=2)
            times=TIMES
            weights=np.array([.5,.5])
            mode=0
            def simulation_gain(self,*args): return 2. if self.mode==0 else .1
            def observation_gain(self,*args): return 1. if self.mode==0 else 4.
        c=Controlled()
        actions=[{'kind':'simulation','theta':[1.,.08,1.4],'fidelity':'high','cost':8},
                 {'kind':'observation','variable':'x','time':2.,'cost':12}]
        first=rank_actions(c,actions,seed=0,step=0)[0]['kind']
        c.mode=1
        second=rank_actions(c,actions,seed=0,step=0)[0]['kind']
        self.assertEqual(first,'simulation'); self.assertEqual(second,'observation')

    def test_negative_gains_still_rank(self):
        class Controlled:
            settings=GPSettings(fantasies=2)
            times=TIMES
            weights=np.array([.5,.5])
            def observation_gain(self,*args): return -1.
        ranked=rank_actions(Controlled(),[{'kind':'observation','variable':'x','time':2.,'cost':12}],seed=0,step=0)
        self.assertLess(ranked[0]['gain_per_credit'],0)


if __name__ == "__main__":
    unittest.main()
