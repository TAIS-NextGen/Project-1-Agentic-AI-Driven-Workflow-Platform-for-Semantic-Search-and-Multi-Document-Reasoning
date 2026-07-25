import styles from './LandingPage.module.css';

interface LandingPageProps {
  onStart: () => void;
}

export function LandingPage({ onStart }: LandingPageProps) {
  return (
    <div className={styles.container}>
      {/* Decorative background glows */}
      <div className={`${styles.glow} ${styles.glow1}`}></div>
      <div className={`${styles.glow} ${styles.glow2}`}></div>

      <header className={styles.header}>
        <div className={styles.logo}>
          <div className={styles.logoMark}>
            <svg width="20" height="20" viewBox="0 0 16 16" fill="none">
              <path d="M3 4.5H10.5M3 8H8M3 11.5H10.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
              <path d="M11.5 6.5L13.5 8L11.5 9.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </div>
          <span className={styles.logoText}>FlowDocs</span>
        </div>
        <button onClick={onStart} className="btn-secondary">Launch App</button>
      </header>

      <main className={styles.heroSection}>
        <div className={styles.heroContent}>
          <div className={styles.badge}>Next-Gen AI Orchestrator</div>
          <h1 className={styles.title}>
            Orchestrate <span className={styles.gradientText}>Agentic Workflows</span> for Document Reasonings
          </h1>
          <p className={styles.subtitle}>
            An AI-driven platform for semantic search, multi-document reasoning, multi-language handwriting OCR, and dynamic document classifiers.
          </p>
          <div className={styles.ctaGroup}>
            <button onClick={onStart} className="btn-premium">
              Get Started Free
              <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M5 12l5-4-5-4" />
              </svg>
            </button>
            <a href="#features" className="btn-secondary">Explore Features</a>
          </div>
        </div>

        {/* Interactive preview box */}
        <div className={styles.heroVisual}>
          <div className={styles.visualCard}>
            <div className={styles.cardHeader}>
              <span className={styles.dot}></span>
              <span className={styles.dot}></span>
              <span className={styles.dot}></span>
              <span className={styles.cardTitle}>Agentic Workflow Canvas</span>
            </div>
            <div className={styles.mockFlow}>
              <div className={`${styles.mockNode} ${styles.preprocessing}`}>
                <div className={styles.nodeIcon}>📄</div>
                <div>
                  <div className={styles.nodeName}>Doc Ingestion</div>
                  <div className={styles.nodeDesc}>24 files loaded</div>
                </div>
              </div>
              <div className={styles.flowLine}></div>
              <div className={`${styles.mockNode} ${styles.ocr}`}>
                <div className={styles.nodeIcon}>👁️</div>
                <div>
                  <div className={styles.nodeName}>Multilingual OCR</div>
                  <div className={styles.nodeDesc}>Success (99.8%)</div>
                </div>
              </div>
              <div className={styles.flowLine}></div>
              <div className={`${styles.mockNode} ${styles.rag}`}>
                <div className={styles.nodeIcon}>🔍</div>
                <div>
                  <div className={styles.nodeName}>Vector RAG</div>
                  <div className={styles.nodeDesc}>Cosine Similarity</div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </main>

      <section id="features" className={styles.featuresSection}>
        <h2 className={styles.sectionTitle}>Engineered for Complex Document Chains</h2>
        <div className={styles.grid}>
          <div className={styles.featureCard}>
            <div className={styles.featIcon}>✨</div>
            <h3>Intelligent Preprocessing</h3>
            <p>Advanced image denoising, text splitting, metadata extraction, and validator controls.</p>
          </div>
          <div className={styles.featureCard}>
            <div className={styles.featIcon}>👁️</div>
            <h3>Handwriting & OCR</h3>
            <p>Convert images to text seamlessly in Arabic, English, and French using state-of-the-art OCR engines.</p>
          </div>
          <div className={styles.featureCard}>
            <div className={styles.featIcon}>🧬</div>
            <h3>Semantic Search & RAG</h3>
            <p>Embed documents using standard vector models and perform hybrid retrieval-augmented generation.</p>
          </div>
          <div className={styles.featureCard}>
            <div className={styles.featIcon}>🔀</div>
            <h3>Logic & Branching</h3>
            <p>Run conditional flows, document classifiers, and export structured outputs like JSON or markdown.</p>
          </div>
        </div>
      </section>

      <footer className={styles.footer}>
        <p>© 2026 FlowDocs Corp. Built with Google Antigravity IDE.</p>
      </footer>
    </div>
  );
}
