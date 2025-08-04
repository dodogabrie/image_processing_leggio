import path, { dirname } from 'path';
import { spawn } from 'child_process';
import { fileURLToPath } from 'url';

// Shim per __dirname in ES module
const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

/**
 * Esegue uno script Python per estrarre i metadata da un file XML e salvarli in JSON.
 * @param {string} inputXml - Percorso al file XML di input
 * @param {string} outputJson - Percorso al file JSON di output
 * @returns {Promise<void>}
 */
export function metadataWorker(inputXml, outputJson) {
  const pythonPath =
    process.platform === 'win32'
      ? path.join(__dirname, '..', '..', 'venv', 'Scripts', 'python.exe')
      : path.join(__dirname, '..', '..', 'venv', 'bin', 'python3');
  const scriptPath = path.join(__dirname, '..', 'scripts', 'extract_metadata.py');

  return new Promise((resolve, reject) => {
    const args = [scriptPath, inputXml, outputJson];
    const child = spawn(pythonPath, args, {
      stdio: ['ignore', 'pipe', 'pipe'],
      windowsHide: true
    });

    child.stdout.on('data', data => process.stdout.write(data.toString()));
    child.stderr.on('data', data => process.stderr.write(data.toString()));

    child.on('exit', code => {
      if (code === 0) resolve();
      else reject(new Error(`extract_metadata.py exited with code ${code}`));
    });
  });
}
