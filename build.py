#!/usr/bin/env python3
import argparse,json,pathlib,re,uuid
from compile_queries import Parser
ROOT=pathlib.Path(__file__).resolve().parent

def uid(s):return str(uuid.uuid5(uuid.NAMESPACE_URL,'jira-elastic-native-v1/'+s))
def walk(ps):
 for p in ps:
  yield p
  yield from walk(p.get('panels',[]))
def object_(kind,id,attrs,refs=None):return dict(type=kind,id=id,attributes=attrs,references=refs or [])
def chart(request,kind,unit):
 data={'name':'results','url':request,'format':{'property':'aggregations.result.value'}}
 # Full Vega supports text marks for metric cards and tabular views.
 common={'$schema':'https://vega.github.io/schema/vega/v5.json','autosize':{'type':'fit','contains':'padding'},'padding':8,'data':[data,{'name':'rows','source':'results','transform':[{'type':'formula','expr':"datum.query + ' | ' + datum.series",'as':'label'},{'type':'collect','sort':{'field':['series','query'],'order':['ascending','ascending']}}]}]}
 if kind in ('table','stat','gauge'):
  common['data'][1]['transform'] += [{'type':'window','ops':['row_number'],'as':['row'],'sort':{'field':['series','query']}}]
  common['signals']=[{'name':'offset','value':0,'on':[{'events':'wheel!','update':'clamp(offset + event.deltaY, 0, max(0, length(data("rows"))*24-height+35))'}]}]
  common['marks']=[{'type':'text','encode':{'update':{'x':{'value':0},'y':{'value':13},'fontWeight':{'value':'bold'},'text':{'value':'Series / query'}}}},{'type':'text','encode':{'update':{'x':{'signal':'width-8'},'y':{'value':13},'align':{'value':'right'},'fontWeight':{'value':'bold'},'text':{'value':'Value ('+unit+')' if unit else 'Value'}}}},{'type':'group','clip':True,'encode':{'update':{'x':{'value':0},'y':{'value':25},'width':{'signal':'width'},'height':{'signal':'height-25'}}},'marks':[{'type':'text','from':{'data':'rows'},'encode':{'update':{'x':{'value':0},'y':{'signal':'datum.row*24-offset'},'text':{'field':'label'},'limit':{'signal':'max(20,width*0.72)'},'fontSize':{'value':11},'tooltip':{'signal':'datum'}}}},{'type':'text','from':{'data':'rows'},'encode':{'update':{'x':{'signal':'width-8'},'y':{'signal':'datum.row*24-offset'},'align':{'value':'right'},'text':{'signal':"format(datum.value, '.5~g')"},'tooltip':{'signal':'datum'}}}}]}]
 else:
  common['data'][1]['transform'].append({'type':'collect','sort':{'field':'time','order':'ascending'}})
  common['scales']=[{'name':'x','type':'time','domain':{'data':'rows','field':'time'},'range':'width'},{'name':'y','type':'linear','domain':{'data':'rows','field':'value'},'nice':True,'zero':False,'range':'height'},{'name':'color','type':'ordinal','domain':{'data':'rows','field':'label'},'range':{'scheme':'tableau10'}}]
  common['axes']=[{'orient':'bottom','scale':'x','labelOverlap':True,'tickCount':5},{'orient':'left','scale':'y','title':unit or None,'grid':True,'tickCount':5}]
  common['marks']=[{'type':'group','from':{'facet':{'name':'line','data':'rows','groupby':'label'}},'marks':[{'type':'line','from':{'data':'line'},'sort':{'field':'datum.time'},'encode':{'update':{'x':{'scale':'x','field':'time'},'y':{'scale':'y','field':'value'},'stroke':{'scale':'color','field':'label'},'strokeWidth':{'value':1.5},'tooltip':{'signal':'datum'}}}},{'type':'symbol','from':{'data':'line'},'encode':{'update':{'x':{'scale':'x','field':'time'},'y':{'scale':'y','field':'value'},'size':{'value':12},'fill':{'scale':'color','field':'label'},'tooltip':{'signal':'datum'}}}}]}]
 common['marks'].append({'type':'text','encode':{'update':{'x':{'signal':'width/2'},'y':{'signal':'height/2'},'align':{'value':'center'},'fill':{'value':'#777'},'text':{'signal':"length(data('rows')) ? '' : 'No matching samples in this time range'"}}}})
 return common

def build(index='jira*',time_field='@timestamp'):
 objects=[];manifest=[];labels={'instance','job','product'};metrics=set();compiled={}
 for file in sorted((ROOT/'source').glob('*.json')):
  d=json.loads(file.read_text())
  for p in walk(d['panels']):
   if p['type'] in ('row','alertlist'):continue
   nodes=[];roots=[]
   for t in p.get('targets',[]):
    if not t.get('expr') or t.get('hide'):continue
    parser=Parser(t['expr']);ns,root=parser.parse();offset=len(nodes)
    for n in ns:
     for field in ('input','left','right'):
      if field in n:n[field]+=offset
    nodes.extend(ns);roots.append({'node':root+offset,'ref':t.get('refId',str(len(roots)))})
    labels.update(parser.labels);metrics.update(parser.metrics)
    labels.update(re.findall(r'{{\s*(\w+)\s*}}',t.get('legendFormat','')))
   compiled[(file.stem,p['id'])]=(nodes,roots)
 labels.discard('__name__')
 map_script=(ROOT/'map.painless').read_text();reduce_script=(ROOT/'reduce.painless').read_text()
 for file in sorted((ROOT/'source').glob('*.json')):
  d=json.loads(file.read_text());slug=file.stem;panels=[];refs=[]
  for p in walk(d['panels']):
   key=slug+'/'+str(p['id']);vid=uid(key)
   if p['type']=='row':continue
   if p['type']=='alertlist':
    state={'title':p['title'],'type':'markdown','params':{'markdown':'### Alert rules\nGrafana alert rules and history are not migrated. Configure Kibana rules separately.','fontSize':14},'aggs':[]}
   else:
    nodes,roots=compiled[(slug,p['id'])]
    if not roots:continue
    leaves=[n for n in nodes if n['op']=='leaf'];leaf_metrics=sorted({n['metric'] for n in leaves})
    body={'size':0,'query':{'bool':{'must':['%dashboard_context-must_clause%'],'must_not':['%dashboard_context-must_not_clause%'],'filter':['%dashboard_context-filter_clause%',{'range':{time_field:{'gte':{'%timefilter%':'min','shift':-10,'unit':'minute'},'lte':{'%timefilter%':'max'}}}},{'bool':{'should':[{'exists':{'field':m}} for m in leaf_metrics],'minimum_should_match':1}}]}},'aggs':{'result':{'scripted_metric':{'init_script':'state.series=new HashMap(); state.count=0;','map_script':map_script,'combine_script':'return state.series;','reduce_script':reduce_script,'params':{'nodes':nodes,'roots':roots,'labels':sorted(labels),'time_field':time_field,'start':{'%timefilter%':'min'},'end':{'%timefilter%':'max'},'snapshot':p['type'] in ('stat','gauge','table'),'points':120,'sample_limit':100000,'output_limit':20000}}}}}
    request={'index':index,'body':body}
    unit=p.get('fieldConfig',{}).get('defaults',{}).get('unit','')
    state={'title':p['title'],'type':'vega','params':{'spec':json.dumps(chart(request,p['type'],unit))},'aggs':[]}
    manifest.append({'dashboard':slug,'panel':p['id'],'title':p['title'],'source_type':p['type'],'metrics':leaf_metrics,'queries':[t['expr'] for t in p['targets'] if t.get('expr') and not t.get('hide')]})
   objects.append(object_('visualization',vid,{'title':'Jira | '+p['title'],'description':'Elasticsearch-only conversion. Original metric/label names. Gauge/stat panels use numeric rows. Scripted metric requires Elasticsearch Stack.','visState':json.dumps(state),'uiStateJSON':'{}','kibanaSavedObjectMeta':{'searchSourceJSON':'{"query":{"query":"","language":"kuery"},"filter":[]}'}}))
   g=p['gridPos'];n=str(len(panels)+1)
   panels.append({'panelIndex':n,'type':'visualization','panelRefName':'panel_'+n,'gridData':{'x':g['x']*2,'y':g['y'],'w':g['w']*2,'h':g['h'],'i':n},'embeddableConfig':{}})
   refs.append({'name':'panel_'+n,'type':'visualization','id':vid})
  objects.append(object_('dashboard',uid(slug),{'title':'Jira | '+slug.replace('-',' ').title(),'description':'Elasticsearch-only Jira metrics. Source: Atlassian Jira Grafana dashboards.','panelsJSON':json.dumps(panels),'optionsJSON':'{"useMargins":true,"hidePanelTitles":false}','timeRestore':True,'timeFrom':'now-1h','timeTo':'now','refreshInterval':{'pause':True,'value':60000},'version':1,'kibanaSavedObjectMeta':{'searchSourceJSON':'{"query":{"query":"","language":"kuery"},"filter":[]}' }},refs))
 (ROOT/'jira-elastic-dashboards.ndjson').write_text(''.join(json.dumps(o)+'\n' for o in objects))
 (ROOT/'conversion-manifest.json').write_text(json.dumps(manifest,indent=2))
 mapping={'properties':{time_field:{'type':'date'},**{m:{'type':'double'} for m in sorted(metrics)},**{l:{'type':'keyword'} for l in sorted(labels)}}}
 (ROOT/'expected-mapping.json').write_text(json.dumps(mapping,indent=2))
 print(f'{len(objects)} objects; {len(manifest)} metric panels; {len(metrics)} metric fields; index {index}')
if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--index',default='jira*');ap.add_argument('--time-field',default='@timestamp');a=ap.parse_args();build(a.index,a.time_field)
