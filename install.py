#!/usr/bin/env python3
"""Resolve the existing Jira data view and import the dashboards into Kibana.
Python 3.10+, no additional packages. Does not read Elasticsearch documents.
"""
import argparse,json,os,pathlib,ssl,urllib.request,uuid
from build import build
ROOT=pathlib.Path(__file__).resolve().parent

def main():
 ap=argparse.ArgumentParser(description=__doc__)
 ap.add_argument('--data-view',default='Jira')
 ap.add_argument('--prepare-only',action='store_true',help='Resolve data view and generate NDJSON without importing')
 ap.add_argument('--overwrite',action='store_true',help='Overwrite this package\'s previously imported deterministic saved-object IDs')
 args=ap.parse_args();base=os.environ['KIBANA_URL'].rstrip('/')
 auth=os.getenv('KIBANA_AUTH','');context=ssl.create_default_context(cafile=os.getenv('CA_CERT') or None)
 def call(path,body=None,content_type='application/json'):
  headers={'kbn-xsrf':'jira-dashboard-import','Content-Type':content_type}
  if auth:headers['Authorization']=auth
  req=urllib.request.Request(base+path,data=body,headers=headers,method='POST' if body is not None else 'GET')
  with urllib.request.urlopen(req,context=context,timeout=180) as response:return json.load(response)
 candidates=call('/api/data_views')['data_view']
 matches=[v for v in candidates if v.get('name')==args.data_view or v.get('title')==args.data_view or v.get('id')==args.data_view]
 if len(matches)!=1:raise SystemExit('Expected one Jira data view. Use --data-view with its exact ID to resolve ambiguity.')
 from urllib.parse import quote
 view=call('/api/data_views/data_view/'+quote(matches[0]['id'],safe=''))['data_view']
 build(index=view['title'],time_field=view.get('timeFieldName') or '@timestamp')
 if args.prepare_only:
  print('Prepared jira-elastic-dashboards.ndjson for your existing data view. No dashboards imported.');return
 boundary='JiraImport'+uuid.uuid4().hex
 body=('--'+boundary+'\r\nContent-Disposition: form-data; name="file"; filename="jira-elastic-dashboards.ndjson"\r\nContent-Type: application/x-ndjson\r\n\r\n').encode()+(ROOT/'jira-elastic-dashboards.ndjson').read_bytes()+('\r\n--'+boundary+'--\r\n').encode()
 result=call('/api/saved_objects/_import?overwrite='+str(args.overwrite).lower(),body,'multipart/form-data; boundary='+boundary)
 (ROOT/'import-result.json').write_text(json.dumps(result,indent=2))
 if not result.get('success'):raise SystemExit('Import reported errors. Inspect import-result.json. Existing objects are not overwritten without --overwrite.')
 print('Imported '+str(result.get('successCount',0))+' objects. Open Dashboards and search Jira |.')
if __name__=='__main__':main()
