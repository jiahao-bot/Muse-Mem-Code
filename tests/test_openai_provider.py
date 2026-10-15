import json
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer

from muse_mem.llm import OpenAICompatibleLLM

class OpenAIProviderTests(unittest.TestCase):
    def test_tool_call_id_and_tool_result_round_trip(self):
        requests = []
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass
            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                requests.append(body)
                if len(requests) == 1:
                    message = {"role": "assistant", "content": None, "tool_calls": [{
                        "id": "call-1", "type": "function",
                        "function": {"name": "read_file", "arguments": '{"path":"user/x.md"}'},
                    }]}
                else:
                    message = {"role": "assistant", "content": "done"}
                payload = json.dumps({"choices": [{"message": message}]}).encode()
                self.send_response(200)
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

        server = HTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            llm = OpenAICompatibleLLM(f"http://127.0.0.1:{server.server_port}/v1",
                                      "test", "model", temperature=1.0)
            first = llm.complete(system="s", messages=[], tools=[{"type": "function", "function": {"name": "read_file"}}])
            self.assertEqual(first.tool_calls[0].call_id, "call-1")
            llm.complete(system="s", messages=[first.assistant_message,
                         {"role": "tool", "tool_call_id": "call-1", "name": "read_file", "content": "{}"}])
            self.assertEqual(requests[0]["temperature"], 1.0)
            self.assertEqual(requests[1]["messages"][-1]["role"], "tool")
            self.assertEqual(requests[1]["messages"][-1]["tool_call_id"], "call-1")
        finally:
            server.shutdown()
            server.server_close()

if __name__ == "__main__":
    unittest.main()
