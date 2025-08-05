import fs from 'fs';
import path, { dirname } from 'path';
import { spawn } from 'child_process';
import { fileURLToPath } from 'url';

// Shim per __dirname in ES module
const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

const venvPath =
  process.env.NODE_ENV === 'development'
    ? null // In development, usa Python di sistema
    : path.join(process.resourcesPath, 'venv');

export function cropWorker(input, output) {
  const pythonPath = process.env.NODE_ENV === 'development'
    ? (process.platform === 'win32' ? 'python' : 'python3') // Python di sistema
    : (process.platform === 'win32'
        ? path.join(venvPath, 'Scripts', 'python.exe')
        : path.join(venvPath, 'bin', 'python3'));

  const scriptPath =
    process.env.NODE_ENV === 'development'
      ? path.join(__dirname, '..', 'scripts', 'crop.py')
      : path.join(
          process.resourcesPath,
          'app.asar.unpacked',
          'src',
          'scripts',
          'crop.py'
        );

  // Salva i log nella stessa cartella dell'output
  const logPath = path.join(path.dirname(output), 'crop_worker.log');

  function log(msg) {
    fs.mkdirSync(path.dirname(logPath), { recursive: true });
    fs.appendFileSync(logPath, `[${new Date().toISOString()}] ${msg}\n`);
  }

  log(
    `START cropWorker: pythonPath=${pythonPath}, scriptPath=${scriptPath}, input=${input}, output=${output}`
  );

  return new Promise((resolve, reject) => {
    const args = [scriptPath, input, output];

    // Controlla che pythonPath esista (solo in produzione)
    if (process.env.NODE_ENV !== 'development' && !fs.existsSync(pythonPath)) {
      log(`ERROR: Python interpreter not found at ${pythonPath}`);
      return reject(new Error(`Python interpreter not found at ${pythonPath}`));
    }
    // Controlla che lo script esista
    if (!fs.existsSync(scriptPath)) {
      log(`ERROR: crop.py not found at ${scriptPath}`);
      return reject(new Error(`crop.py not found at ${scriptPath}`));
    }

    const child = spawn(pythonPath, args, {
      stdio: ['ignore', 'pipe', 'pipe'],
      windowsHide: true,
    });

    child.stdout.on('data', data => {
      log(`STDOUT: ${data.toString()}`);
    });
    child.stderr.on('data', data => {
      log(`STDERR: ${data.toString()}`);
    });

    child.on('error', err => {
      log(`SPAWN ERROR: ${err.message}`);
      reject(err);
    });

    child.on('exit', code => {
      log(`EXIT CODE: ${code}`);
      if (code === 0) resolve();
      else {
        log(`ERROR: crop.py exited with code ${code}`);
        resolve();
      }
    });
  });
}
