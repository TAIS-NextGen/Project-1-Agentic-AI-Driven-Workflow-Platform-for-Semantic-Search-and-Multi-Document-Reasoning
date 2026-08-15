import { useEffect, useRef, useState } from 'react';
import { askQuestion, getQaStats, type QaAskResponse } from '../../services/backendApi';
import styles from './QAChatView.module.css';

interface Message {
  role: 'user' | 'assistant';
  text: string;
  chunks?: Array<{ chunk_text: string; filename: string; score: number }>;
}

export function QAChatView() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [stats, setStats] = useState<{ documents: number; chunks: number } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  const refreshStats = async () => {
    try {
      setStats(await getQaStats());
    } catch {
      setStats(null);
    }
  };

  useEffect(() => {
    refreshStats();
  }, []);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, loading]);

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    const question = input.trim();
    if (!question || loading) return;

    setInput('');
    setError(null);
    setMessages((prev) => [...prev, { role: 'user', text: question }]);
    setLoading(true);

    try {
      const response: QaAskResponse = await askQuestion(question);
      setMessages((prev) => [
        ...prev,
        { role: 'assistant', text: response.answer, chunks: response.retrieved_chunks },
      ]);
      await refreshStats();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to get an answer.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className={styles.page}>
      <header className={styles.header}>
        <span>RAG</span>
        <h1>QA Chat</h1>
        <p>Ask questions over your indexed document library.</p>
        {stats && (
          <div className={styles.stats}>
            <span>{stats.documents} document{stats.documents === 1 ? '' : 's'} indexed</span>
            <span>{stats.chunks} chunks</span>
          </div>
        )}
      </header>

      <div className={styles.chat}>
        {messages.length === 0 && !loading && (
          <div className={styles.empty}>
            <p>Upload documents (Documents page) and index them, then ask a question.</p>
            <small>The first question auto-indexes the library if it is not yet indexed.</small>
          </div>
        )}

        {messages.map((message, index) => (
          <div key={index} className={`${styles.message} ${styles[message.role]}`}>
            <div className={styles.messageLabel}>{message.role === 'user' ? 'You' : 'Assistant'}</div>
            <div className={styles.bubble}>{message.text}</div>
            {message.chunks && message.chunks.length > 0 && (
              <div className={styles.chunks}>
                {message.chunks.slice(0, 3).map((chunk, ci) => (
                  <div key={ci} className={styles.chunk}>
                    <span className={styles.chunkScore}>{chunk.score.toFixed(2)}</span>
                    <span className={styles.chunkFile}>{chunk.filename}</span>
                    <span className={styles.chunkText}>{chunk.chunk_text}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        ))}

        {loading && (
          <div className={`${styles.message} ${styles.assistant}`}>
            <div className={styles.messageLabel}>Assistant</div>
            <div className={styles.bubble}>{'Thinking…'}</div>
          </div>
        )}

        {error && <div className={styles.error}>{error}</div>}
        <div ref={bottomRef} />
      </div>

      <form className={styles.form} onSubmit={handleSubmit}>
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask a question about your documents…"
          className={styles.input}
          disabled={loading}
        />
        <button type="submit" className={styles.send} disabled={loading || !input.trim()}>
          Send
        </button>
      </form>
    </div>
  );
}
