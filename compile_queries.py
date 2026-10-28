"""Parse only the PromQL subset actually used by the pinned Jira dashboards."""
import json,re
TOKEN=re.compile(r'\s*(?:(\d+(?:\.\d+)?)|([A-Za-z_:][A-Za-z0-9_:]*)|("(?:\\.|[^"\\])*")|(.))')
class Parser:
 def __init__(self,expr):
  expr=re.sub(r'#[^\n]*','',expr)
  self.t=[next(x for x in m.groups() if x is not None) for m in TOKEN.finditer(expr) if m.group(4) is None or not m.group(4).isspace()];self.i=0;self.nodes=[];self.labels=set();self.metrics=set()
 def peek(self):return self.t[self.i] if self.i<len(self.t) else ''
 def take(self,s=None):
  x=self.peek()
  if not x or (s and x!=s):raise ValueError(f'Expected {s}, got {x}; {self.t[self.i:]}')
  self.i+=1;return x
 def add(self,n):self.nodes.append(n);return len(self.nodes)-1
 def expr(self,minimum=0):
  a=self.primary()
  while self.peek() in ('+','-','*','/') and {'+':1,'-':1,'*':2,'/':2}[self.peek()]>=minimum:
   op=self.take();b=self.expr({'+':1,'-':1,'*':2,'/':2}[op]+1);a=self.add({'op':'binary','operator':op,'left':a,'right':b})
  return a
 def primary(self):
  x=self.take()
  if x=='(':
   a=self.expr();self.take(')');return a
  if re.fullmatch(r'\d+(\.\d+)?',x):return self.add({'op':'number','value':float(x)})
  if x in ('sum','avg','max'):
   mode=self.take();assert mode in ('by','without');self.take('(');labels=[]
   while self.peek()!=')':
    labels.append(self.take())
    if self.peek()!=',':break
    self.take(',')
   self.take(')');self.take('(');a=self.expr();self.take(')');self.labels.update(labels)
   return self.add({'op':'aggregate','fn':x,'mode':mode,'labels':labels,'input':a})
  if x in ('rate','increase','delta'):
   self.take('(');a=self.primary();self.take(')');assert self.nodes[a]['op']=='leaf';self.nodes[a]['fn']=x;return a
  if x=='topk':
   self.take('(');n=int(self.take());self.take(',');a=self.expr();self.take(')');return self.add({'op':'topk','n':n,'input':a})
  if x=='time':self.take('(');self.take(')');return self.add({'op':'time'})
  labels={};self.take('{')
  while self.peek()!='}':
   k=self.take();self.take('=');labels[k]=json.loads(self.take())
   if self.peek()!=',':break
   self.take(',')
  self.take('}');window=0
  if self.peek()=='[':
   self.take('[');n=float(self.take());u=self.take();self.take(']');window=int(n*{'m':60000,'s':1000,'h':3600000}[u])
  self.labels.update(labels);self.metrics.add(x)
  return self.add({'op':'leaf','metric':x,'match':labels,'window':window,'fn':'instant'})
 def parse(self):
  root=self.expr()
  if self.i!=len(self.t):raise ValueError('Trailing tokens: '+str(self.t[self.i:]))
  return self.nodes,root
