import fs from 'node:fs';
import path from 'node:path';
import { spawn } from 'node:child_process';

const frontendDir = process.cwd();
const backendDir = path.resolve(frontendDir, '../backend');
const appPath = path.resolve(backendDir, 'app.py');

function candidatePythonPaths() {
  const candidates = [];
  const venvNames = ['venv', '.venv'];

  for (const venvName of venvNames) {
    // macOS/Linux
    candidates.push(path.join(backendDir, venvName, 'bin', 'python3'));
    candidates.push(path.join(backendDir, venvName, 'bin', 'python'));
    // Windows
    candidates.push(path.join(backendDir, venvName, 'Scripts', 'python.exe'));
  }

  // Allow override if you want to force a specific interpreter.
  if (process.env.E2E_PYTHON && process.env.E2E_PYTHON.trim()) {
    candidates.push(process.env.E2E_PYTHON.trim());
  }

  // Fallbacks
  candidates.push('python3');
  candidates.push('python');

  return candidates;
}

function pickPythonExecutable() {
  for (const candidate of candidatePythonPaths()) {
    // If it's a bare command like "python3", just try it.
    if (!candidate.includes(path.sep)) return candidate;
    if (fs.existsSync(candidate)) return candidate;
  }
  return 'python3';
}

if (!fs.existsSync(appPath)) {
  console.error(`[e2e-backend] Could not find backend app at: ${appPath}`);
  process.exit(1);
}

const pythonExe = pickPythonExecutable();
console.log(`[e2e-backend] Using python: ${pythonExe}`);
console.log(`[e2e-backend] Starting: ${appPath}`);

const child = spawn(pythonExe, [appPath], {
  stdio: 'inherit',
  env: {
    ...process.env,
    PORT: process.env.PORT || '5001',
  },
});

child.on('exit', (code, signal) => {
  if (signal) {
    console.log(`[e2e-backend] Exited with signal: ${signal}`);
    process.exit(1);
  }
  process.exit(code ?? 1);
});

process.on('SIGTERM', () => child.kill('SIGTERM'));
process.on('SIGINT', () => child.kill('SIGINT'));

