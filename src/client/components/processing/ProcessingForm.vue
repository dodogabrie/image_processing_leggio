<template>
  <div>
    <div class="mb-3">
      <button class="btn btn-primary me-2" @click="processing.selectFolder">Seleziona cartella</button>
      <span v-if="processing.selectedFolder.value" class="fst-italic text-secondary">
        Cartella selezionata: {{ processing.selectedFolder.value }}
      </span>
    </div>

    <div class="mb-3">
      <button class="btn btn-secondary me-2" @click="processing.selectOutput">Seleziona cartella output</button>
      <span v-if="processing.selectedOutput.value" class="fst-italic text-secondary">
        Output: {{ processing.selectedOutput.value }}
      </span>
    </div>

    <div class="form-check mb-3">
      <input class="form-check-input" type="checkbox" id="optimizeImagesCheckbox" v-model="processing.optimizeImages.value" />
      <label class="form-check-label" for="optimizeImagesCheckbox">
        Ottimizza Immagini
        <small class="text-muted d-block">
          Se disabilitato, verrà eseguita solo l'organizzazione CSV (richiede immagini già processate in output)
        </small>
      </label>
    </div>

    <div class="form-check mb-3" v-if="processing.optimizeImages.value">
      <input class="form-check-input" type="checkbox" id="previewModeCheckbox" v-model="processing.previewMode.value" />
      <label class="form-check-label" for="previewModeCheckbox">
        Modalità Anteprima
        <small class="text-muted d-block">
          Elabora solo 4 immagini per testare le dimensioni finali. I risultati verranno eliminati automaticamente dopo 60 secondi.
        </small>
      </label>
    </div>

    <div class="mb-3" v-if="processing.optimizeImages.value">
      <label class="form-label">Aggressività elaborazione:</label>
      <div class="d-flex gap-3">
        <div class="form-check">
          <input class="form-check-input" type="radio" name="aggressivity" id="aggressivityLow" value="low" v-model="processing.aggressivity.value" />
          <label class="form-check-label" for="aggressivityLow">
            Bassa
            <small class="text-muted d-block">Bilanciamento qualità/dimensioni</small>
          </label>
        </div>
        <div class="form-check">
          <input class="form-check-input" type="radio" name="aggressivity" id="aggressivityStandard" value="standard" v-model="processing.aggressivity.value" />
          <label class="form-check-label" for="aggressivityStandard">
            Standard
            <small class="text-muted d-block">Compressione buona, file ridotti</small>
          </label>
        </div>
        <div class="form-check">
          <input class="form-check-input" type="radio" name="aggressivity" id="aggressivityHigh" value="high" v-model="processing.aggressivity.value" />
          <label class="form-check-label" for="aggressivityHigh">
            Alta
            <small class="text-muted d-block">Compressione massima, file molto piccoli</small>
          </label>
        </div>
      </div>
    </div>

    <div class="form-check mb-3" v-if="processing.optimizeImages.value">
      <input class="form-check-input" type="checkbox" id="cropCheckbox" v-model="processing.crop.value" />
      <label class="form-check-label" for="cropCheckbox">Abilita crop immagini</label>
    </div>

    <div class="form-check mb-3" v-if="processing.optimizeImages.value">
      <input class="form-check-input" type="checkbox" id="optimizeVideosCheckbox" v-model="processing.optimizeVideos.value" />
      <label class="form-check-label" for="optimizeVideosCheckbox">
        Ottimizza video
        <small class="text-muted d-block">
          Se disabilitato, i video verranno solo copiati. FFmpeg è incluso nell'applicazione.
        </small>
      </label>
    </div>

    <div class="mb-3" v-if="processing.showCsvInput.value">
      <label class="form-label">
        Fermati alla riga CSV n°:
        <input
          type="number"
          v-model.number="processing.maxCsvLine.value"
          min="1"
          class="form-control d-inline-block"
          style="width:100px;"
          placeholder="(tutte)"
        />
      </label>
    </div>

    <div class="mb-3">
      <button class="btn btn-success me-2" :disabled="!processing.selectedFolder.value || processing.processing.value" @click="handleStartProcess">
        Processa
      </button>
      <button class="btn btn-danger" :disabled="!processing.processing.value" @click="processing.stopProcess">Ferma</button>
    </div>
  </div>
</template>

<script setup>
import { inject } from 'vue'

const processing = inject('processing')
const explorer = inject('explorer')

const handleStartProcess = async () => {
  const res = await processing.startProcess()

  if (res.success) {
    const outputDir = res.outputDir || processing.selectedOutput.value || processing.selectedFolder.value
    // Set original folder automatically for comparison
    explorer.originalRoot.value = processing.selectedFolder.value || explorer.originalRoot.value
    await explorer.initializeExplorer(outputDir, res.organizedDir, res.organizedThumbsDir)
  }
}
</script>
