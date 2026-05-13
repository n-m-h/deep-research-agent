<template>
  <div class="app">
    <div class="container">
      <div class="hero">
        <h1>🔍 深度研究助手</h1>
        <p>自动化深度研究智能体，让知识获取更高效</p>
      </div>
      
      <div class="search-card">
        <div class="input-group">
          <input 
            v-model="topic" 
            type="text" 
            placeholder="输入研究主题，例如：Datawhale是一个什么样的组织？"
            @keyup.enter="handleResearch"
            :disabled="isLoading"
          />
          <button @click="handleResearch" :disabled="isLoading || !topic.trim()">
            {{ isLoading ? '研究中...' : '开始研究' }}
          </button>
        </div>
        
        <div class="features">
          <div class="feature">
            <span class="icon">📚</span>
            <span>智能规划</span>
          </div>
          <div class="feature">
            <span class="icon">🔗</span>
            <span>多源搜索</span>
          </div>
          <div class="feature">
            <span class="icon">📊</span>
            <span>结构化报告</span>
          </div>
        </div>
      </div>

      <div class="rag-card">
        <div class="rag-header" @click="showRagPanel = !showRagPanel">
          <span>📄 个人知识库</span>
          <span class="rag-toggle">{{ showRagPanel ? '▲' : '▼' }}</span>
        </div>

        <div v-if="showRagPanel" class="rag-body">
          <div class="rag-controls">
            <label class="rag-switch">
              <input type="checkbox" v-model="useRag" />
              <span class="switch-slider"></span>
              <span class="switch-label">研究中同时查询个人文档</span>
            </label>
          </div>

          <div
            class="upload-zone"
            @dragover.prevent
            @drop.prevent="handleDrop"
            @click="triggerUpload"
          >
            <input
              ref="fileInput"
              type="file"
              accept=".pdf,.txt,.md,.docx"
              multiple
              style="display: none"
              @change="handleFileSelect"
            />
            <div class="upload-icon">📤</div>
            <div class="upload-text">
              {{ isUploading ? '上传中...' : '拖拽或点击上传文档' }}
            </div>
            <div class="upload-hint">支持 PDF / TXT / MD / DOCX</div>
          </div>

          <div v-if="uploadError" class="upload-error">{{ uploadError }}</div>

          <div v-if="documents.length > 0" class="doc-list">
            <div v-for="doc in documents" :key="doc.doc_id" class="doc-item">
              <div class="doc-info">
                <span class="doc-icon">📄</span>
                <div class="doc-meta">
                  <div class="doc-name">{{ doc.filename }}</div>
                  <div class="doc-chunks">{{ doc.chunk_count }} 个片段</div>
                </div>
              </div>
              <button class="doc-delete" @click="deleteDocument(doc.doc_id)">🗑️</button>
            </div>
          </div>

          <div v-else class="doc-empty">
            <p>还没有上传文档</p>
            <p class="doc-empty-hint">上传后，研究时自动检索您个人文档中的相关内容</p>
          </div>

          <div class="rag-status">
            <span v-if="documents.length > 0" class="status-badge active">
              ✅ {{ documents.length }} 篇文档已索引
            </span>
            <span v-else class="status-badge inactive">
              ⚡ 等待上传
            </span>
          </div>
        </div>
      </div>
    </div>
    
    <ResearchModal 
      :isOpen="isOpen"
      :researchTopic="researchTopic"
      :progressPercentage="progressPercentage"
      :progressText="progressText"
      :markdownContent="markdownContent"
      :isLoading="isLoading"
      @close="closeModal"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import ResearchModal from './components/ResearchModal.vue'
import { useResearch } from './composables/useResearch'

const topic = ref('')
const showRagPanel = ref(true)
const fileInput = ref<HTMLInputElement | null>(null)

const { 
  isOpen,
  isLoading,
  researchTopic,
  progressPercentage,
  progressText,
  markdownContent,
  useRag,
  documents,
  isUploading,
  uploadError,
  startResearch,
  fetchDocuments,
  uploadDocument,
  deleteDocument,
  close: closeModal
} = useResearch()

onMounted(() => {
  fetchDocuments()
})

const handleResearch = () => {
  if (!topic.value.trim() || isLoading.value) return
  startResearch(topic.value)
}

const triggerUpload = () => {
  fileInput.value?.click()
}

const handleFileSelect = async (event: Event) => {
  const target = event.target as HTMLInputElement
  if (target.files) {
    for (const file of target.files) {
      await uploadDocument(file)
    }
    target.value = ''
  }
}

const handleDrop = async (event: DragEvent) => {
  if (event.dataTransfer?.files) {
    for (const file of event.dataTransfer.files) {
      await uploadDocument(file)
    }
  }
}
</script>

<style>
* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  min-height: 100vh;
}

.app {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 20px;
}

.container {
  max-width: 700px;
  width: 100%;
}

.hero {
  text-align: center;
  margin-bottom: 40px;
  color: white;
}

.hero h1 {
  font-size: 48px;
  font-weight: 700;
  margin-bottom: 12px;
  text-shadow: 0 2px 4px rgba(0,0,0,0.1);
}

.hero p {
  font-size: 18px;
  opacity: 0.9;
}

.search-card {
  background: white;
  border-radius: 16px;
  padding: 32px;
  box-shadow: 0 20px 40px rgba(0,0,0,0.15);
}

.input-group {
  display: flex;
  gap: 12px;
  margin-bottom: 24px;
}

.input-group input {
  flex: 1;
  padding: 16px 20px;
  font-size: 16px;
  border: 2px solid #e5e7eb;
  border-radius: 10px;
  outline: none;
  transition: border-color 0.2s;
}

.input-group input:focus {
  border-color: #667eea;
}

.input-group input:disabled {
  background: #f9fafb;
  cursor: not-allowed;
}

.input-group button {
  padding: 16px 32px;
  font-size: 16px;
  font-weight: 600;
  color: white;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  border: none;
  border-radius: 10px;
  cursor: pointer;
  transition: transform 0.2s, box-shadow 0.2s;
}

.input-group button:hover:not(:disabled) {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(102, 126, 234, 0.4);
}

.input-group button:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.features {
  display: flex;
  justify-content: center;
  gap: 32px;
}

.feature {
  display: flex;
  align-items: center;
  gap: 8px;
  color: #6b7280;
  font-size: 14px;
}

.icon {
  font-size: 18px;
}

.rag-card {
  background: white;
  border-radius: 16px;
  margin-top: 16px;
  box-shadow: 0 20px 40px rgba(0,0,0,0.15);
  overflow: hidden;
}

.rag-header {
  padding: 16px 24px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  cursor: pointer;
  font-weight: 600;
  font-size: 16px;
  color: #374151;
  user-select: none;
  transition: background 0.2s;
}

.rag-header:hover {
  background: #f9fafb;
}

.rag-toggle {
  color: #9ca3af;
  font-size: 12px;
}

.rag-body {
  padding: 0 24px 20px;
}

.rag-controls {
  margin-bottom: 16px;
}

.rag-switch {
  display: flex;
  align-items: center;
  gap: 10px;
  cursor: pointer;
}

.rag-switch input {
  display: none;
}

.switch-slider {
  width: 40px;
  height: 22px;
  background: #d1d5db;
  border-radius: 11px;
  position: relative;
  transition: background 0.3s;
}

.switch-slider::after {
  content: '';
  position: absolute;
  width: 18px;
  height: 18px;
  border-radius: 50%;
  background: white;
  top: 2px;
  left: 2px;
  transition: transform 0.3s;
}

.rag-switch input:checked + .switch-slider {
  background: #667eea;
}

.rag-switch input:checked + .switch-slider::after {
  transform: translateX(18px);
}

.switch-label {
  font-size: 14px;
  color: #6b7280;
}

.upload-zone {
  border: 2px dashed #d1d5db;
  border-radius: 12px;
  padding: 24px;
  text-align: center;
  cursor: pointer;
  transition: all 0.3s;
  margin-bottom: 12px;
}

.upload-zone:hover {
  border-color: #667eea;
  background: #f5f3ff;
}

.upload-icon {
  font-size: 32px;
  margin-bottom: 8px;
}

.upload-text {
  font-size: 14px;
  font-weight: 600;
  color: #374151;
  margin-bottom: 4px;
}

.upload-hint {
  font-size: 12px;
  color: #9ca3af;
}

.upload-error {
  color: #ef4444;
  font-size: 13px;
  padding: 8px;
  background: #fef2f2;
  border-radius: 8px;
  margin-bottom: 12px;
}

.doc-list {
  margin-top: 16px;
}

.doc-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 12px;
  background: #f9fafb;
  border-radius: 8px;
  margin-bottom: 8px;
  transition: background 0.2s;
}

.doc-item:hover {
  background: #f3f4f6;
}

.doc-info {
  display: flex;
  align-items: center;
  gap: 10px;
}

.doc-icon {
  font-size: 20px;
}

.doc-meta {
  line-height: 1.4;
}

.doc-name {
  font-size: 14px;
  font-weight: 500;
  color: #374151;
}

.doc-chunks {
  font-size: 12px;
  color: #9ca3af;
}

.doc-delete {
  background: none;
  border: none;
  cursor: pointer;
  padding: 4px 8px;
  border-radius: 4px;
  transition: background 0.2s;
}

.doc-delete:hover {
  background: #fee2e2;
}

.doc-empty {
  text-align: center;
  padding: 20px;
  color: #9ca3af;
}

.doc-empty p {
  margin: 4px 0;
}

.doc-empty-hint {
  font-size: 12px;
}

.rag-status {
  margin-top: 12px;
}

.status-badge {
  display: inline-block;
  padding: 4px 12px;
  border-radius: 20px;
  font-size: 12px;
  font-weight: 500;
}

.status-badge.active {
  background: #ecfdf5;
  color: #059669;
}

.status-badge.inactive {
  background: #f3f4f6;
  color: #6b7280;
}

@media (max-width: 640px) {
  .hero h1 {
    font-size: 32px;
  }
  
  .hero p {
    font-size: 16px;
  }
  
  .input-group {
    flex-direction: column;
  }
  
  .input-group button {
    width: 100%;
  }
  
  .features {
    flex-direction: column;
    gap: 12px;
    align-items: center;
  }
}
</style>
