// Script per preparare i binari FFmpeg durante la build
import { execSync } from 'child_process';
import { existsSync, mkdirSync, copyFileSync } from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));

console.log('[prepare-ffmpeg] Preparing FFmpeg binaries for build...');

// Determina le piattaforme da preparare
// In development o quando non specificato, prepara solo per la piattaforma corrente
const targetPlatform = process.env.BUILD_PLATFORM || process.platform;

// Directory di output per i binari
const buildFFmpegDir = path.join(process.cwd(), 'build-ffmpeg');

// Funzione per copiare i binari FFmpeg dalla dipendenza installata
function prepareFfmpegBinaries() {
  console.log(`[prepare-ffmpeg] Preparing binaries for platform: ${targetPlatform}`);

  // Crea directory per piattaforma
  const platformDir = path.join(buildFFmpegDir, targetPlatform);
  if (!existsSync(platformDir)) {
    mkdirSync(platformDir, { recursive: true });
  }

  try {
    // Importa il package FFmpeg installer
    const ffmpegPath = execSync('node -p "require(\'@ffmpeg-installer/ffmpeg\').path"', {
      encoding: 'utf-8'
    }).trim().replace(/['"]/g, '');

    console.log(`[prepare-ffmpeg] Found FFmpeg at: ${ffmpegPath}`);

    if (!existsSync(ffmpegPath)) {
      throw new Error(`FFmpeg binary not found at: ${ffmpegPath}`);
    }

    // Determina il nome del binario di destinazione
    const binaryName = targetPlatform === 'win32' ? 'ffmpeg.exe' : 'ffmpeg';
    const destPath = path.join(platformDir, binaryName);

    // Copia il binario
    copyFileSync(ffmpegPath, destPath);
    console.log(`[prepare-ffmpeg] Copied FFmpeg to: ${destPath}`);

    // Su Linux/Mac, rendi il file eseguibile
    if (targetPlatform !== 'win32') {
      try {
        execSync(`chmod +x "${destPath}"`);
        console.log(`[prepare-ffmpeg] Made FFmpeg executable`);
      } catch (error) {
        console.warn(`[prepare-ffmpeg] Warning: Could not set executable permission: ${error.message}`);
      }
    }

    // Verifica che il file esista
    if (!existsSync(destPath)) {
      throw new Error('FFmpeg binary copy failed');
    }

    console.log(`[prepare-ffmpeg] ✓ FFmpeg binaries prepared successfully for ${targetPlatform}`);

  } catch (error) {
    console.error(`[prepare-ffmpeg] Failed to prepare FFmpeg binaries:`, error.message);
    throw error;
  }
}

// Esegui la preparazione
prepareFfmpegBinaries();

console.log('[prepare-ffmpeg] FFmpeg preparation completed');
console.log(`[prepare-ffmpeg] Output directory: ${buildFFmpegDir}`);
