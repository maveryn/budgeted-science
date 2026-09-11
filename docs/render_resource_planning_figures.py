"""Render curated SVG figures from saved results, without numerical dependencies.

This is documentation-only; it never imports the scientific environment, runs
a policy, or changes source results. PNG previews may be rendered with any SVG
renderer. Usage: python docs/render_resource_planning_figures.py RUN --output-dir DIR
"""
import argparse
import hashlib
import json
from pathlib import Path
from xml.etree import ElementTree as ET


def resource_figure(summary):
    ns="http://www.w3.org/2000/svg"
    root=ET.Element('svg', {'xmlns':ns, 'width':'900', 'height':'350', 'viewBox':'0 0 900 350'})
    def add(tag, **attrs):
        return ET.SubElement(root,tag,{k.replace('_','-'):str(v) for k,v in attrs.items()})
    def label(x,y,text,**attrs):
        attributes={'x':x,'y':y,'font_family':'Arial, sans-serif','font_size':14,'fill':'#263238'}
        attributes.update(attrs)
        element=add('text',**attributes)
        element.text=text
    add('rect',x=0,y=0,width=900,height=350,fill='white')
    label(450,32,'Where the 40 scientific credits went',font_weight='bold',font_size=22,text_anchor='middle')
    label(450,57,'Mean over all episodes; paid initialization included',font_size=13,text_anchor='middle')
    left,width=210,640
    keys=[('simulate_low_credits','Cheap simulations','#4e79a7'),
          ('simulate_high_credits','Accurate simulations','#e18b34'),
          ('measure_target_credits','Target measurements','#479a77')]
    for row,policy in enumerate(('random','adaptive')):
        y=96+row*78
        p=summary['policies'][policy]
        label(left-16,y+28,'Fixed / randomized' if policy=='random' else 'Cost-aware adaptive',text_anchor='end')
        offset=0.
        for key,name,color in keys:
            stats=p['resources'].get(key,{})
            if stats.get('count')!=p['attempts'] or stats.get('mean') is None:
                raise ValueError('resource figure requires known spending for every episode')
            value=stats['mean']; segment=width*value/40
            add('rect',x=left+offset,y=y,width=segment,height=42,fill=color)
            label(left+offset+segment/2,y+27,f'{value:.2f}',fill='white',font_weight='bold',text_anchor='middle')
            offset+=segment
        label(left+width,y+58,f"n = {p['attempts']}",font_size=12,text_anchor='end')
    axis_y=248
    add('line',x1=left,y1=axis_y,x2=left+width,y2=axis_y,stroke='#333')
    for value in range(0,41,10):
        x=left+width*value/40
        add('line',x1=x,y1=axis_y,x2=x,y2=axis_y+5,stroke='#333')
        label(x,axis_y+22,str(value),font_size=12,text_anchor='middle')
    label(left+width/2,axis_y+43,'Scientific credits (represented resource costs)',font_size=13,text_anchor='middle')
    for i,(_,name,color) in enumerate(keys):
        x=135+i*235
        add('rect',x=x,y=316,width=14,height=14,fill=color)
        label(x+22,328,name,font_size=13)
    return ET.tostring(root,encoding='unicode')+'\n'


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('run',type=Path)
    parser.add_argument('--output-dir',type=Path,required=True)
    args=parser.parse_args()
    run=args.run.resolve(); output=args.output_dir.resolve()
    if output==run or output.is_relative_to(run/'attempts'):
        raise ValueError('figure output must be separate from canonical records')
    report=run/'report'
    source=report/'summary.json'
    summary=json.loads(source.read_text(encoding='utf-8'))
    completion=json.loads((run/'completion.json').read_text(encoding='utf-8'))
    if not completion.get('complete') or completion.get('source_unchanged') is not True:
        raise ValueError('curated figures require a complete run with unchanged scientific sources')
    output.mkdir(parents=True,exist_ok=True)
    figures={'paired_errors.svg':(report/'paired_errors.svg').read_text(encoding='utf-8'),
             'resource_allocation.svg':resource_figure(summary)}
    for name,content in figures.items():
        (output/name).write_text(content,encoding='utf-8',newline='\n')
    provenance={'run_id':run.name,'summary_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
                'renderer_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                'scientific_provenance':summary['provenance'],'completion':completion,
                'figures':{name:hashlib.sha256((output/name).read_bytes()).hexdigest() for name in figures}}
    (output/'provenance.json').write_text(json.dumps(provenance,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'output':str(output),**provenance},indent=2))


if __name__=='__main__':
    main()
