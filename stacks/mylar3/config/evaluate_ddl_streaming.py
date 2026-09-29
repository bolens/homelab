"""Bounded fixture demonstrating why full curl streaming stays unavailable."""
import json,threading,time
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from curl_cffi import requests
SIZE=16*1024*1024
class Handler(BaseHTTPRequestHandler):
 def log_message(self,*args):pass
 def do_GET(self):
  self.send_response(200);self.send_header('Content-Length',str(SIZE));self.end_headers()
  block=b'x'*65536
  try:
   for _ in range(SIZE//len(block)):self.wfile.write(block)
  except (BrokenPipeError,ConnectionResetError):pass
server=ThreadingHTTPServer(('127.0.0.1',0),Handler);t=threading.Thread(target=server.serve_forever,daemon=True);t.start()
try:
 with requests.Session(retry=0) as s:
  r=s.get('http://127.0.0.1:'+str(server.server_port),stream=True,timeout=(1,2))
  deadline=time.monotonic()+3
  while r.queue.qsize()<=64 and time.monotonic()<deadline: time.sleep(.05)
  print(json.dumps({'max_queue':r.queue.maxsize,'queued_chunks':r.queue.qsize(),'fixture_bytes':SIZE}))
  assert r.queue.maxsize==0 and r.queue.qsize()>64
  before=time.monotonic();r.close();assert time.monotonic()-before<4
finally:server.shutdown();server.server_close();t.join()
