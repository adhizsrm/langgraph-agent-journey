import shutil
import subprocess
import time
import threading
import json
import re
import platform
from typing import List, Dict, Any


def run_server_smoke_test(
    cmd_list: List[str], cwd: str, api_contract: Any = None, timeout: int = 10
) -> Dict[str, Any]:
    npm_path = shutil.which(cmd_list[0]) or cmd_list[0]
    actual_cmd = [npm_path] + cmd_list[1:]

    start_time = time.time()
    proc = subprocess.Popen(
        actual_cmd,
        cwd=cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
    )

    stdout_lines = []
    stderr_lines = []

    def reader(pipe, lines_list):
        for line in iter(pipe.readline, ""):
            if not line:
                break
            lines_list.append(line.rstrip())
        pipe.close()

    t_out = threading.Thread(
        target=reader, args=(proc.stdout, stdout_lines), daemon=True
    )
    t_err = threading.Thread(
        target=reader, args=(proc.stderr, stderr_lines), daemon=True
    )
    t_out.start()
    t_err.start()

    startup_verified = False
    process_exited = False
    success_patterns = [
        "server running",
        "server started",
        "listening",
        "ready in",
        "http://",
        "accepting connections",
    ]

    while time.time() - start_time < timeout:
        if proc.poll() is not None:
            process_exited = True
            break

        found = False
        for line in stdout_lines[-20:]:  # check recent lines
            lower_line = line.lower()
            if any(p in lower_line for p in success_patterns):
                found = True
                break

        if found:
            startup_verified = True
            break
        time.sleep(0.1)

    crud_errors = []
    if startup_verified and api_contract and getattr(api_contract, "operations", []):
        import urllib.request
        import urllib.error

        port = 3000
        for line in stdout_lines:
            port_match = re.search(r"port\s*:?\s*(\d+)", line, re.IGNORECASE)
            if port_match:
                port = int(port_match.group(1))
                break

        base_route = api_contract.base_route.replace("//", "/").rstrip("/")
        if not base_route.startswith("/"):
            base_route = "/" + base_route
        url = f"http://127.0.0.1:{port}{base_route}"

        post_payload = {"title": "Smoke Test Note", "content": "Created by executor"}
        put_payload = {
            "title": "Updated Smoke Test Note",
            "content": "Updated by executor",
        }
        note_id = None

        def do_request(method, path, payload=None):
            req = urllib.request.Request(path, method=method)
            if payload:
                req.data = json.dumps(payload).encode()
                req.add_header("Content-Type", "application/json")
            try:
                with urllib.request.urlopen(req, timeout=3) as res:
                    return res.status, res.read().decode()
            except urllib.error.HTTPError as e:
                return e.code, e.read().decode()
            except Exception as e:
                return 0, str(e)

        # 1. POST
        status, body_str = do_request("POST", url, post_payload)
        if status not in [200, 201]:
            crud_errors.append(
                f"EXECUTION FAILURE:\\nOperation: Create Note\\nRequest: POST {url}\\nRequest body:\\n{json.dumps(post_payload)}\\nResponse status: {status}\\nResponse body:\\n{body_str}"
            )
        else:
            try:
                body_json = json.loads(body_str)
                note_id = body_json.get("id") or body_json.get("_id")
            except:
                pass

            # 2. GET
            status, body_str = do_request("GET", url)
            if status != 200:
                crud_errors.append(
                    f"EXECUTION FAILURE:\\nOperation: Read Notes\\nRequest: GET {url}\\nResponse status: {status}\\nResponse body:\\n{body_str}"
                )

            # 3. PUT
            if note_id:
                put_url = f"{url}/{note_id}"
                status, body_str = do_request("PUT", put_url, put_payload)
                if status not in [200, 201]:
                    crud_errors.append(
                        f"EXECUTION FAILURE:\\nOperation: Update Note\\nRequest: PUT {put_url}\\nRequest body:\\n{json.dumps(put_payload)}\\nResponse status: {status}\\nResponse body:\\n{body_str}"
                    )

                # 4. DELETE
                del_url = f"{url}/{note_id}"
                status, body_str = do_request("DELETE", del_url)
                if status not in [200, 204]:
                    crud_errors.append(
                        f"EXECUTION FAILURE:\\nOperation: Delete Note\\nRequest: DELETE {del_url}\\nResponse status: {status}\\nResponse body:\\n{body_str}"
                    )

    if proc.poll() is None:
        try:
            if platform.system() == "Windows":
                subprocess.run(
                    ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            else:
                proc.terminate()
                proc.wait(timeout=3)
        except:
            if proc.poll() is None:
                proc.kill()

    t_out.join(timeout=1.0)
    t_err.join(timeout=1.0)

    end_time = time.time()
    exit_code = proc.returncode

    if exit_code is not None and exit_code != 0 and not startup_verified:
        return {
            "success": False,
            "startup_verified": False,
            "exit_code": exit_code,
            "stdout": "\\n".join(stdout_lines),
            "stderr": "\\n".join(stderr_lines),
            "duration": end_time - start_time,
            "error": "Backend crashed during startup",
        }

    if startup_verified:
        if crud_errors:
            return {
                "success": False,
                "startup_verified": True,
                "exit_code": exit_code,
                "stdout": "\\n".join(stdout_lines),
                "stderr": "\\n".join(stderr_lines),
                "duration": end_time - start_time,
                "error": "\\n\\n".join(crud_errors),
            }

        return {
            "success": True,
            "startup_verified": True,
            "exit_code": exit_code,
            "stdout": "\\n".join(stdout_lines),
            "stderr": "\\n".join(stderr_lines),
            "duration": end_time - start_time,
        }

    return {
        "success": False,
        "startup_verified": False,
        "exit_code": exit_code,
        "stdout": "\\n".join(stdout_lines),
        "stderr": "\\n".join(stderr_lines),
        "duration": end_time - start_time,
        "error": "Timeout reached without establishing readiness (No startup log detected)",
    }
