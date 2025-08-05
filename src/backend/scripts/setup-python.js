import { execSync } from 'child_process';
import { existsSync, mkdirSync } from 'fs';
import path from 'path';

const venvPath = process.env.NODE_ENV === 'development'
  ? path.join(process.cwd(), 'venv')
  : path.join(process.resourcesPath, 'venv');

export function setupPythonEnv() {
  const pipDir = process.platform === 'win32' ? 'Scripts' : 'bin';
  const pipPath = path.join(
    venvPath,
    pipDir,
    process.platform === 'win32' ? 'pip.exe' : 'pip'
  );
  const pythonPath = path.join(
    venvPath,
    pipDir,
    process.platform === 'win32' ? 'python.exe' : 'python3'
  );

  // Se l'ambiente virtuale esiste già, non fare nulla
  if (existsSync(pipPath) && existsSync(pythonPath)) return;

  console.log(`[setup-python] Creating virtual environment at: ${venvPath}`);
  
  // Assicurati che la directory padre esista
  mkdirSync(path.dirname(venvPath), { recursive: true });

  console.log('Creating virtualenv...');
  execSync(
    `${process.platform === 'win32' ? 'python' : 'python3'} -m venv "${venvPath}"`,
    {
      cwd: path.dirname(venvPath),
      stdio: 'inherit'
    }
  );

  // Determina il percorso corretto di requirements.txt
  const requirementsPath = process.env.NODE_ENV === 'development'
    ? path.join(process.cwd(), 'requirements.txt')
    : path.join(process.resourcesPath, 'app.asar.unpacked', 'requirements.txt');

  console.log(`Installing Python dependencies from: ${requirementsPath}`);
  execSync(`"${pipPath}" install -r "${requirementsPath}"`, {
    stdio: 'inherit'
  });

  console.log('[setup-python] Virtual environment created successfully');
}
