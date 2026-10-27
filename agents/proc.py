"""Child-process helpers shared by the coding-agent runners (Claude Code, Codex)."""
import os
import subprocess


def kill_tree(p):
    """Stop a process AND everything it started. Coding agents run measure commands (Python + Blender):
    killing only the CLI left Blender rendering in the background, holding the workspace's files open."""
    if p.poll() is not None:
        return
    if os.name == "nt":
        subprocess.run(["taskkill", "/PID", str(p.pid), "/T", "/F"], capture_output=True)
    else:
        try:
            os.killpg(os.getpgid(p.pid), 9)
        except (OSError, AttributeError):
            pass
    if p.poll() is None:
        p.kill()


def run_tree(cmd, input_text, cwd, env, timeout, label="process"):
    """subprocess.run(..., capture_output=True, text=True) whose timeout kills the whole process tree
    and raises RuntimeError (a TimeoutExpired escaped the callers' error handling)."""
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                         encoding="utf-8", errors="replace", cwd=cwd, env=env, start_new_session=os.name != "nt")
    try:
        out, err = p.communicate(input_text, timeout=timeout)
    except subprocess.TimeoutExpired:
        kill_tree(p)
        p.communicate()
        raise RuntimeError(f"{label} timed out after {timeout:.0f} s and was stopped with everything it started")
    return subprocess.CompletedProcess(cmd, p.returncode, out, err)
