import { useState, useRef, useEffect } from 'react';
import { Bot, User, Send, UploadCloud, FileText, Sparkles, Zap, Code2, Loader2, CheckCircle2 } from 'lucide-react';
import './index.css';

const API_BASE = 'http://127.0.0.1:8000';

type Role = 'user' | 'ai' | 'agent' | 'system';

interface Message {
  id: string;
  role: Role;
  content: string;
  elapsed?: number;
  isCached?: boolean;
}

function App() {
  const [messages, setMessages] = useState<Message[]>([{
    id: 'init',
    role: 'ai',
    content: '안녕하세요! On-Device AI 시스템입니다. 일반 질문, RAG 문서 기반 질문, 혹은 코드를 작성하고 샌드박스에서 검증하는 자율 에이전트 기능을 사용해보세요.',
  }]);
  const [input, setInput] = useState('');
  const [isAgentMode, setIsAgentMode] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [uploadStatus, setUploadStatus] = useState<{status: 'idle' | 'uploading' | 'success' | 'error', msg: string}>({status: 'idle', msg: ''});
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, isLoading]);

  const handleSend = async () => {
    if (!input.trim() || isLoading) return;
    
    const userMsg: Message = { id: Date.now().toString(), role: 'user', content: input };
    setMessages(prev => [...prev, userMsg]);
    setInput('');
    setIsLoading(true);

    const endpoint = isAgentMode ? '/agent' : '/chat';
    
    try {
      const res = await fetch(`${API_BASE}${endpoint}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ prompt: userMsg.content })
      });
      
      const data = await res.json();
      
      if (!res.ok) {
        throw new Error(data.detail || 'API 통신 오류가 발생했습니다.');
      }
      
      const aiMsg: Message = {
        id: (Date.now() + 1).toString(),
        role: isAgentMode ? 'agent' : 'ai',
        content: data.response,
        elapsed: data.elapsed_seconds,
        isCached: data.is_cached || data.source === 'cache'
      };
      
      setMessages(prev => [...prev, aiMsg]);
    } catch (err: any) {
      setMessages(prev => [...prev, { id: Date.now().toString(), role: 'system', content: `[에러] ${err.message}` }]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setUploadStatus({ status: 'uploading', msg: `${file.name} 업로드 중... Phase 2 백그라운드 엔진 가동` });
    
    const formData = new FormData();
    formData.append('file', file);

    try {
      const res = await fetch(`${API_BASE}/upload`, {
        method: 'POST',
        body: formData,
      });
      
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || '업로드 실패');
      
      setUploadStatus({ status: 'success', msg: `✅ ${data.filename} - 지식베이스 인제스천 성공 (백그라운드 그래프 연산 중)` });
      
      setTimeout(() => setUploadStatus({ status: 'idle', msg: '' }), 5000);
      
    } catch (err: any) {
      setUploadStatus({ status: 'error', msg: `❌ 업로드 실패: ${err.message}` });
    }
    
    if (e.target) {
      e.target.value = '';
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className="app-container">
      {/* Sidebar */}
      <aside className="sidebar">
        <div className="brand">
          <Bot className="brand-icon" size={28} />
          <span>Antigravity</span>
        </div>

        <div style={{ marginBottom: '2rem' }}>
          <div className="mode-toggle" onClick={() => setIsAgentMode(!isAgentMode)}>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
              <span style={{ fontSize: '0.9rem', fontWeight: 600, color: isAgentMode ? '#f43f5e' : '#e2e8f0', display: 'flex', alignItems: 'center', gap: '6px' }}>
                {isAgentMode ? <Code2 size={16} /> : <Sparkles size={16} />}
                {isAgentMode ? '코드 에이전트 모드' : '일반 & RAG 채팅'}
              </span>
              <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                {isAgentMode ? '샌드박스에서 코드를 실행합니다' : '빠른 질의응답을 처리합니다'}
              </span>
            </div>
            <div className={`toggle-switch ${isAgentMode ? 'active' : ''}`} />
          </div>
        </div>

        <div className="upload-section">
          <input type="file" className="upload-input" onChange={handleFileUpload} />
          {uploadStatus.status === 'uploading' ? (
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '8px' }}>
              <Loader2 className="spinner" size={24} color="#6366f1" />
              <span style={{ fontSize: '0.85rem', color: '#a5b4fc' }}>파일 분석 중...</span>
            </div>
          ) : uploadStatus.status === 'success' ? (
             <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '8px' }}>
             <CheckCircle2 size={24} color="#10b981" />
             <span style={{ fontSize: '0.85rem', color: '#6ee7b7' }}>지식 주입 진행 중</span>
           </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '8px', color: 'var(--text-muted)' }}>
              <UploadCloud size={28} />
              <span style={{ fontSize: '0.9rem', fontWeight: 500 }}>RAG 문서 업로드</span>
              <span style={{ fontSize: '0.75rem' }}>드래그하거나 클릭하여 파일 선택</span>
            </div>
          )}
        </div>
        
        {uploadStatus.msg && uploadStatus.status !== 'idle' && (
          <div style={{ fontSize: '0.75rem', padding: '10px', background: 'rgba(0,0,0,0.3)', borderRadius: '8px', borderLeft: `3px solid ${uploadStatus.status === 'error' ? '#ef4444' : '#6366f1'}`, color: '#e2e8f0', lineHeight: 1.5 }}>
            {uploadStatus.msg}
          </div>
        )}

      </aside>

      {/* Main Chat Area */}
      <main className="chat-container">
        
        <div className="chat-messages">
          {messages.map((msg) => (
            <div key={msg.id} className={`message-wrapper ${msg.role === 'user' ? 'user' : 'ai'}`}>
              <div className={`avatar ${msg.role}`}>
                {msg.role === 'user' ? <User size={20} color="#fff" /> : 
                 msg.role === 'agent' ? <Code2 size={20} color="#fff" /> : 
                 <Bot size={20} color="#fff" />}
              </div>
              
              <div style={{ display: 'flex', flexDirection: 'column', alignItems: msg.role === 'user' ? 'flex-end' : 'flex-start' }}>
                <div className="message-bubble">
                  {msg.content}
                </div>
                
                {(msg.elapsed || msg.isCached) && (
                  <div className="meta-footer">
                    {msg.isCached && (
                      <span className="badge hit"><Zap size={12} /> Semantic Cache Hit</span>
                    )}
                    {msg.elapsed && (
                      <span className="badge"><FileText size={12} /> {msg.elapsed}초 소요</span>
                    )}
                  </div>
                )}
              </div>
            </div>
          ))}
          
          {isLoading && (
            <div className="message-wrapper ai">
              <div className="avatar ai">
                <Loader2 size={18} className="spinner" color="#fff" />
              </div>
              <div className="typing-indicator">
                {isAgentMode ? '에이전트가 코드를 작성하고 샌드박스를 실행 중입니다' : 'AI가 지식을 검색하고 추론 중입니다'}
                <div className="typing-dots">
                  <span/><span/><span/>
                </div>
              </div>
            </div>
          )}
          
          <div ref={messagesEndRef} />
        </div>

        {/* Input Block */}
        <div className="input-area">
          <div className="input-container">
            <textarea
              className="chat-input"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder={isAgentMode ? "에이전트에게 파이썬 코드 작성을 요청해보세요... (예: 1부터 10까지 곱하는 코드 짜서 결과 알려줘)" : "궁금한 것을 물어보세요..."}
              disabled={isLoading}
              rows={1}
            />
            <button 
              className="send-btn" 
              onClick={handleSend}
              disabled={!input.trim() || isLoading}
            >
              <Send size={20} />
            </button>
          </div>
        </div>
      </main>
    </div>
  );
}

export default App;
