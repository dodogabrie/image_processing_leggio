// Script per preparare l'ambiente Python durante la build
import { execSync } from 'child_process';
import { existsSync, mkdirSync } from 'fs';
import path from 'path';

const venvPath = path.join(process.cwd(), 'build-venv');
const requirementsPath = path.join(process.cwd(), 'requirements.txt');

console.log('[prepare-python] Preparing Python environment for build...');

// Crea l'ambiente virtuale temporaneo
if (!existsSync(venvPath)) {
  console.log(`[prepare-python] Creating virtual environment at: ${venvPath}`);
  execSync(
    `${process.platform === 'win32' ? 'python' : 'python3'} -m venv "${venvPath}"`,
    { stdio: 'inherit' }
  );
}

// Installa le dipendenze
const pipDir = process.platform === 'win32' ? 'Scripts' : 'bin';
const pipPath = path.join(venvPath, pipDir, process.platform === 'win32' ? 'pip.exe' : 'pip');

if (existsSync(requirementsPath)) {
  console.log(`[prepare-python] Installing dependencies from: ${requirementsPath}`);
  execSync(`"${pipPath}" install -r "${requirementsPath}"`, { stdio: 'inherit' });
}

console.log('[prepare-python] Python environment prepared successfully');

// Verifica che tutto sia stato creato correttamente
const pythonPath2 = path.join(venvPath, pipDir, process.platform === 'win32' ? 'python.exe' : 'python3');

console.log(`[prepare-python] Verification:`);
console.log(`[prepare-python] - pip exists: ${existsSync(pipPath)}`);
console.log(`[prepare-python] - python exists: ${existsSync(pythonPath2)}`);
console.log(`[prepare-python] - venv path: ${venvPath}`);

if (!existsSync(pipPath) || !existsSync(pythonPath2)) {
  throw new Error('Virtual environment creation failed - missing executables');
}
