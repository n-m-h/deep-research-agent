import { ref, computed } from 'vue'

interface Task {
  id: number
  title: string
  intent: string
  query: string
  status?: string
}

interface ResearchEvent {
  type: string
  message?: string
  data?: any
  task_id?: number
  percentage?: number
  stage?: string
}

interface DocumentInfo {
  doc_id: string
  filename: string
  chunk_count: number
  upload_time: string
}

export function useResearch() {
  const isLoading = ref(false)
  const isOpen = ref(false)
  const researchTopic = ref('')
  const progressPercentage = ref(0)
  const progressText = ref('')
  const currentStage = ref('')
  const markdownContent = ref('')
  const error = ref<string | null>(null)
  const tasks = ref<Task[]>([])
  const useRag = ref(true)

  const documents = ref<DocumentInfo[]>([])
  const isUploading = ref(false)
  const uploadError = ref<string | null>(null)

  const renderedMarkdown = computed(() => {
    return markdownContent.value
  })

  const fetchDocuments = async () => {
    try {
      const response = await fetch('http://localhost:8000/documents')
      const data = await response.json()
      documents.value = data.documents || []
    } catch (e) {
      console.error('获取文档列表失败:', e)
    }
  }

  const uploadDocument = async (file: File) => {
    isUploading.value = true
    uploadError.value = null
    try {
      const formData = new FormData()
      formData.append('file', file)
      const response = await fetch('http://localhost:8000/documents/upload', {
        method: 'POST',
        body: formData,
      })
      if (!response.ok) {
        const err = await response.json()
        throw new Error(err.detail || '上传失败')
      }
      await fetchDocuments()
      return true
    } catch (e: any) {
      uploadError.value = e.message
      return false
    } finally {
      isUploading.value = false
    }
  }

  const deleteDocument = async (docId: string) => {
    try {
      await fetch(`http://localhost:8000/documents/${docId}`, {
        method: 'DELETE',
      })
      await fetchDocuments()
    } catch (e) {
      console.error('删除文档失败:', e)
    }
  }

  const startResearch = async (topic: string) => {
    researchTopic.value = topic
    isOpen.value = true
    isLoading.value = true
    error.value = null
    progressPercentage.value = 0
    progressText.value = '正在连接...'
    markdownContent.value = ''
    tasks.value = []

    try {
      const response = await fetch('http://localhost:8000/research/stream', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ topic, use_rag: useRag.value }),
      })

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`)
      }

      const reader = response.body?.getReader()
      if (!reader) {
        throw new Error('No response body')
      }

      const decoder = new TextDecoder()
      let buffer = ''

      while (true) {
        const { done, value } = await reader.read()
        
        if (done) {
          console.log('Stream done, buffer:', buffer.length, buffer.substring(0, 100))
          if (buffer.trim().startsWith('data: ')) {
            const jsonStr = buffer.trim().slice(6)
            try {
              const data: ResearchEvent = JSON.parse(jsonStr)
              if (data.type === 'report') {
                if (data.data?.report) {
                  markdownContent.value = data.data.report
                }
                isLoading.value = false
                progressPercentage.value = 100
                progressText.value = '研究完成！'
              }
            } catch (e) {
              console.error('解析buffer数据失败:', e)
            }
          }
          break
        }

        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() || ''

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const jsonStr = line.slice(6)
              const data: ResearchEvent = JSON.parse(jsonStr)
              
              switch (data.type) {
                case 'status':
                  progressText.value = data.message || ''
                  if (data.percentage !== undefined) {
                    progressPercentage.value = data.percentage
                  }
                  currentStage.value = data.stage || ''
                  break
                
                case 'tasks':
                  if (data.data?.tasks) {
                    tasks.value = data.data.tasks
                  }
                  break
                
                case 'task_progress':
                  break
                
                case 'task_summary':
                  if (data.data?.summary) {
                    const taskId = data.task_id
                    markdownContent.value += `\n\n## 任务${taskId}\n\n${data.data.summary}\n\n---\n`
                  }
                  break
                
                case 'report':
                  console.log('收到 report 事件:', data.type, data.percentage, data.stage)
                  if (data.data?.report) {
                    console.log('报告内容长度:', data.data.report.length)
                    markdownContent.value = data.data.report
                  }
                  if (data.percentage !== undefined) {
                    progressPercentage.value = data.percentage
                  }
                  if (data.stage === 'completed') {
                    console.log('报告完成，设置状态')
                    isLoading.value = false
                    progressPercentage.value = 100
                    progressText.value = '研究完成！'
                  }
                  break
                
                case 'error':
                  error.value = data.message || '发生错误'
                  isLoading.value = false
                  break
                
                case 'completed':
                  isLoading.value = false
                  progressPercentage.value = 100
                  progressText.value = '研究完成！'
                  break
              }
            } catch (e) {
              console.error('解析SSE数据失败:', e, line)
            }
          }
        }
      }

      isLoading.value = false
      progressPercentage.value = 100
      progressText.value = '研究完成！'
      
    } catch (e) {
      console.error('请求失败:', e)
      error.value = '请求失败，请检查后端服务'
      isLoading.value = false
    }
  }

  const close = () => {
    isOpen.value = false
    isLoading.value = false
    markdownContent.value = ''
    tasks.value = []
  }

  return {
    isOpen,
    isLoading,
    researchTopic,
    progressPercentage,
    progressText,
    currentStage,
    markdownContent,
    renderedMarkdown,
    error,
    tasks,
    useRag,
    documents,
    isUploading,
    uploadError,
    startResearch,
    fetchDocuments,
    uploadDocument,
    deleteDocument,
    close,
  }
}
