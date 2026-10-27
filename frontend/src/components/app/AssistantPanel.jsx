import { useState, useRef, useEffect } from 'react'
import { MessageSquare, X, Send, Loader2 } from 'lucide-react'
import { useAppState } from '@/state/AppState'
import { queryNL } from '@/api'

export default function AssistantPanel({ isOpen, onClose }) {
  const { currentUser } = useAppState()
  const [messages, setMessages] = useState([
    { role: 'assistant', text: `Hello. I am the RailOpt Operational Assistant. I can help with information related to ${currentUser?.label || 'all departments'}.` }
  ])
  const [input, setInput] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const messagesEndRef = useRef(null)

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }

  useEffect(() => {
    if (isOpen) scrollToBottom()
  }, [messages, isOpen])

  const quickQuestions = [
    "What are today's important issues?",
    "Why is this issue high priority?",
    "What should I inspect first?",
    "Which tasks need attention?",
    "What happened in this section?",
    "What should my department do?"
  ]

  const handleSubmit = async (e, text = input) => {
    e?.preventDefault()
    if (!text.trim() || isLoading) return

    const userMsg = text.trim()
    setInput('')
    setMessages(prev => [...prev, { role: 'user', text: userMsg }])
    setIsLoading(true)

    try {
      const res = await queryNL(userMsg)
      setMessages(prev => [...prev, { role: 'assistant', text: res.data.answer }])
    } catch (err) {
      console.error(err)
      setMessages(prev => [...prev, { role: 'assistant', text: "Sorry, I couldn't reach the backend to process your request." }])
    } finally {
      setIsLoading(false)
    }
  }

  if (!isOpen) return null

  return (
    <div className="fixed inset-y-0 right-0 z-[9999] flex w-96 max-w-full flex-col border-l border-line bg-surface text-ink shadow-2xl">
      <div className="flex items-center justify-between border-b border-line bg-bar px-5 py-4 text-onbar">
        <div>
          <h2 className="font-semibold tracking-wide uppercase flex items-center gap-2">
            <MessageSquare size={16} />
            RAILOPT ASSISTANT
          </h2>
          <span className="mt-0.5 block text-[10px] uppercase tracking-widest text-barmuted">AI Co-pilot</span>
        </div>
        <button type="button" onClick={onClose} aria-label="Close assistant" className="text-barmuted transition-colors hover:text-onbar">
          <X size={20} />
        </button>
      </div>

      <div className="flex-1 overflow-y-auto p-5">
        <div className="space-y-6">
          {messages.map((msg, i) => (
            <div key={i} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
              <div className={`max-w-[85%] rounded-lg p-3 text-sm ${
                msg.role === 'user' 
                  ? 'bg-info text-white' 
                  : 'bg-raised border border-line text-ink'
              }`}>
                {msg.text}
              </div>
            </div>
          ))}
          {isLoading && (
            <div className="flex justify-start">
              <div className="max-w-[85%] rounded-lg p-3 text-sm bg-raised border border-line text-ink flex items-center gap-2">
                <Loader2 size={14} className="animate-spin text-muted" />
                <span className="text-muted italic">Thinking...</span>
              </div>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>
      </div>

      <div className="border-t border-line bg-raised p-4">
        {messages.length === 1 && (
          <div className="mb-4 flex flex-wrap gap-2">
            {quickQuestions.map((q) => (
              <button
                key={q}
                onClick={() => handleSubmit(null, q)}
                className="rounded border border-line bg-surface px-2.5 py-1.5 text-left text-[11px] font-medium tracking-wide text-muted transition-colors hover:border-info hover:text-info"
              >
                {q}
              </button>
            ))}
          </div>
        )}

        <form onSubmit={handleSubmit} className="relative">
          <input
            type="text"
            placeholder="Ask about the network..."
            value={input}
            onChange={(e) => setInput(e.target.value)}
            disabled={isLoading}
            className="w-full rounded-md border border-line bg-surface py-2.5 pl-3 pr-10 text-sm outline-none transition-colors placeholder:text-faint focus:border-info disabled:opacity-50"
          />
          <button
            type="submit"
            disabled={!input.trim() || isLoading}
            className="absolute right-2 top-1/2 -translate-y-1/2 text-muted transition-colors hover:text-info disabled:opacity-30 disabled:hover:text-muted"
            aria-label="Send message"
          >
            <Send size={16} />
          </button>
        </form>
      </div>
    </div>
  )
}
