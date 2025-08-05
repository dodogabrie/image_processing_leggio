import { execSync } from 'child_process';
import { existsSync, mkdirSync } from 'fs';
import path from 'path';

export async function setupPythonEnv() {
  // In development, non fare nulla - usa Python di sistema
  if (process.env.NODE_ENV === 'development') {
    console.log('[setup-python] Development mode: skipping virtual environment setup');
    return;
  }

  // In produzione, verifica se l'ambiente virtuale esiste già
  try {
    const venvPath = path.join(process.resourcesPath, 'venv');
    const pipDir = process.platform === 'win32' ? 'Scripts' : 'bin';
    const pipPath = path.join(venvPath, pipDir, process.platform === 'win32' ? 'pip.exe' : 'pip');
    const pythonPath = path.join(venvPath, pipDir, process.platform === 'win32' ? 'python.exe' : 'python3');

    console.log(`[setup-python] Checking virtual environment at: ${venvPath}`);
    console.log(`[setup-python] Looking for pip at: ${pipPath}`);
    console.log(`[setup-python] Looking for python at: ${pythonPath}`);

    // Se l'ambiente virtuale esiste già, tutto OK
    if (existsSync(pipPath) && existsSync(pythonPath)) {
      console.log('[setup-python] Virtual environment found and ready');
      return;
    }

    // Se manca qualcosa, lista cosa c'è nella directory
    console.log(`[setup-python] Virtual environment incomplete. Contents of ${venvPath}:`);
    if (existsSync(venvPath)) {
      const fs = await import('fs/promises');
      const contents = await fs.readdir(venvPath, { recursive: true });
      console.log(contents);
    } else {
      console.log('[setup-python] Virtual environment directory does not exist');
    }

    throw new Error(`Virtual environment incomplete. pip exists: ${existsSync(pipPath)}, python exists: ${existsSync(pythonPath)}`);
    
  } catch (err) {
    console.error('[setup-python] Error:', err.message);
    throw err;
  }
}
