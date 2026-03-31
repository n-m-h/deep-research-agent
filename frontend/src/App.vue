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
import { ref } from 'vue'
import ResearchModal from './components/ResearchModal.vue'
import { useResearch } from './composables/useResearch'

const topic = ref('')

const { 
  isOpen,
  isLoading,
  researchTopic,
  progressPercentage,
  progressText,
  markdownContent,
  startResearch,
  close: closeModal
} = useResearch()

const handleResearch = () => {
  if (!topic.value.trim() || isLoading.value) return
  startResearch(topic.value)
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
