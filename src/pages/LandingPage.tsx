import { useState, useEffect, useRef, type FormEvent } from 'react';
import VideoBackground from "../components/VideoBackground";
import { Link, useNavigate } from 'react-router-dom';
import { api } from '@/api/client';
import {
  Shield,
  Truck,
  MapPin,
  BarChart3,
  Users,
  Zap,
  ArrowRight,
  ChevronRight,
  ExternalLink,
  MessageCircle,
  Send,
  X,
} from 'lucide-react';

/* ────────────────────────── Intersection Observer Hook ────────────────────── */
function useInView(threshold = 0.15) {
  const ref = useRef<HTMLDivElement>(null);
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const obs = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setVisible(true);
          obs.disconnect();
        }
      },
      { threshold }
    );
    obs.observe(el);
    return () => obs.disconnect();
  }, [threshold]);

  return { ref, visible };
}

/* ────────────────────────── Animated Counter ─────────────────────────────── */
function AnimatedCounter({
  end,
  suffix = '',
  duration = 2000,
}: {
  end: number;
  suffix?: string;
  duration?: number;
}) {
  const [count, setCount] = useState(0);
  const { ref, visible } = useInView();

  useEffect(() => {
    if (!visible) return;
    let start = 0;
    const step = end / (duration / 16);
    const timer = setInterval(() => {
      start += step;
      if (start >= end) {
        setCount(end);
        clearInterval(timer);
      } else {
        setCount(Math.floor(start));
      }
    }, 16);
    return () => clearInterval(timer);
  }, [visible, end, duration]);

  return (
    <div ref={ref} className="stat-value">
      {count.toLocaleString()}
      {suffix}
    </div>
  );
}

/* ────────────────────────── Feature Card ─────────────────────────────────── */
function FeatureCard({
  icon,
  color,
  title,
  desc,
  delay,
}: {
  icon: React.ReactNode;
  color: string;
  title: string;
  desc: string;
  delay: number;
}) {
  const { ref, visible } = useInView();

  return (
    <div
      ref={ref}
      className={`feature-card glass animate-in ${visible ? 'visible' : ''}`}
      style={{ transitionDelay: `${delay}ms` }}
    >
      <div className={`feature-icon ${color}`}>{icon}</div>
      <h3 className="feature-title">{title}</h3>
      <p className="feature-desc">{desc}</p>
    </div>
  );
}

/* ────────────────────────── Main App ─────────────────────────────────────── */
export default function LandingPage() {
  const [scrolled, setScrolled] = useState(false);
  const [chatOpen, setChatOpen] = useState(false);
  const [chatInput, setChatInput] = useState('');
  const [chatMessages, setChatMessages] = useState<
    Array<{ role: 'user' | 'assistant'; content: string }>
  >([]);
  const [chatLoading, setChatLoading] = useState(false);
  const [chatError, setChatError] = useState<string | null>(null);
  const navigate = useNavigate();

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 40);
    window.addEventListener('scroll', onScroll, { passive: true });
    return () => window.removeEventListener('scroll', onScroll);
  }, []);

  const scrollToSection = (id: string) => {
    document.getElementById(id)?.scrollIntoView({ behavior: 'smooth' });
  };

  const sendChatMessage = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const message = chatInput.trim();
    if (!message || chatLoading) return;

    setChatMessages(current => [...current, { role: 'user', content: message }]);
    setChatInput('');
    setChatError(null);
    setChatLoading(true);
    try {
      const response = await api.chat(message);
      setChatMessages(current => [
        ...current,
        { role: 'assistant', content: response.reply },
      ]);
    } catch (error) {
      setChatError(error instanceof Error ? error.message : 'Unable to send chat message.');
    } finally {
      setChatLoading(false);
    }
  };

  const features = [
    {
      icon: <Shield size={24} />,
      color: 'purple',
      title: 'Blockchain Verified',
      desc: 'Every donation and supply delivery is recorded on an immutable blockchain ledger for total transparency.',
    },
    {
      icon: <Truck size={24} />,
      color: 'green',
      title: 'Smart Logistics',
      desc: 'AI-powered routing ensures relief supplies reach affected zones via the fastest, safest routes available.',
    },
    {
      icon: <MapPin size={24} />,
      color: 'amber',
      title: 'Real-Time Mapping',
      desc: 'Live disaster maps with crowd-sourced data help responders and donors see exactly where help is needed.',
    },
    {
      icon: <BarChart3 size={24} />,
      color: 'cyan',
      title: 'Impact Analytics',
      desc: 'Comprehensive dashboards track funds, supplies, and outcomes so every stakeholder sees measurable impact.',
    },
    {
      icon: <Users size={24} />,
      color: 'pink',
      title: 'Community Coordination',
      desc: 'Connect NGOs, volunteers, and local authorities through a unified platform for faster disaster response.',
    },
    {
      icon: <Zap size={24} />,
      color: 'red',
      title: 'Rapid Deployment',
      desc: 'One-click emergency activation deploys resources instantly when disaster strikes — every second counts.',
    },
  ];

  return (
    <>
      {/* ── Video Background ── */}
      <VideoBackground />

      {/* ── Navigation ── */}
      <nav className={`navbar ${scrolled ? 'scrolled' : ''}`} id="navbar">
        <Link to="/" className="nav-logo">
          <span className="nav-logo-icon">⛓</span>
          ReliefChain
        </Link>
        <ul className="nav-links">
          <li>
            <a href="#features" onClick={event => { event.preventDefault(); scrollToSection('features'); }}>Features</a>
          </li>
          <li>
            <a href="#how-it-works" onClick={event => { event.preventDefault(); scrollToSection('how-it-works'); }}>How It Works</a>
          </li>
          <li>
            <a href="#impact" onClick={event => { event.preventDefault(); scrollToSection('impact'); }}>Impact</a>
          </li>
          <li>
            <a href="#about" onClick={event => { event.preventDefault(); scrollToSection('about'); }}>About</a>
          </li>
        </ul>
        <button className="nav-cta" id="nav-get-started" onClick={() => navigate('/funds')}>
          Get Started <ChevronRight size={16} />
        </button>
      </nav>

      {/* ── Hero ── */}
      <section className="hero" id="hero">
        <div className="hero-content">
          <div className="hero-badge">
            <span className="hero-badge-dot" />
            Disaster Relief Redefined
          </div>

          <h1 className="hero-title">
            Transparent Aid,
            <br />
            <span className="highlight">Powered by Blockchain</span>
          </h1>

          <p className="hero-subtitle">
            ReliefChain connects donors, responders, and communities through a
            decentralized platform — ensuring every resource reaches those who
            need it most, with full traceability.
          </p>

          <div className="hero-actions">
            <button className="btn btn-primary" id="hero-donate-btn" onClick={() => navigate('/funds')}>
              Start Donating <ArrowRight size={18} />
            </button>
            <button className="btn btn-outline" id="hero-learn-btn" onClick={() => scrollToSection('features')}>
              Learn More <ExternalLink size={16} />
            </button>
          </div>

          {/* Stats */}
          <div className="stats-bar">
            <div className="stat-item">
              <AnimatedCounter end={12500} suffix="+" />
              <div className="stat-label">Lives Impacted</div>
            </div>
            <div className="stat-item">
              <AnimatedCounter end={340} suffix="+" />
              <div className="stat-label">Relief Missions</div>
            </div>
            <div className="stat-item">
              <AnimatedCounter end={98} suffix="%" />
              <div className="stat-label">Fund Transparency</div>
            </div>
            <div className="stat-item">
              <AnimatedCounter end={45} suffix="+" />
              <div className="stat-label">Partner NGOs</div>
            </div>
          </div>
        </div>
      </section>

      {/* ── Features ── */}
      <section className="section" id="features">
        <div className="section-header">
          <span className="section-tag">Core Capabilities</span>
          <h2 className="section-title">
            Everything You Need for Effective Relief
          </h2>
          <p className="section-desc">
            From verifiable donations to AI-driven logistics, ReliefChain
            provides the complete toolkit for modern disaster management.
          </p>
        </div>
        <div className="features-grid">
          {features.map((f, i) => (
            <FeatureCard key={f.title} {...f} delay={i * 100} />
          ))}
        </div>
      </section>

      {/* ── Impact ── */}
      <section className="section" id="impact">
        <div className="section-header">
          <span className="section-tag">Our Impact</span>
          <h2 className="section-title">Relief that reaches people</h2>
          <p className="section-desc">
            Track the people, missions, and partners supported by transparent relief operations.
          </p>
        </div>
        <div className="stats-bar impact-stats">
          <div className="stat-item">
            <AnimatedCounter end={12500} suffix="+" />
            <div className="stat-label">Lives Impacted</div>
          </div>
          <div className="stat-item">
            <AnimatedCounter end={340} suffix="+" />
            <div className="stat-label">Relief Missions</div>
          </div>
          <div className="stat-item">
            <AnimatedCounter end={98} suffix="%" />
            <div className="stat-label">Fund Transparency</div>
          </div>
          <div className="stat-item">
            <AnimatedCounter end={45} suffix="+" />
            <div className="stat-label">Partner NGOs</div>
          </div>
        </div>
      </section>

      {/* ── CTA ── */}
      <section className="cta-section" id="how-it-works">
        <div className="cta-card glass">
          <span className="section-tag">Join the Movement</span>
          <h2 className="cta-title">
            Ready to Make a <span className="highlight">Difference</span>?
          </h2>
          <p className="cta-desc">
            Whether you're a donor, NGO, or volunteer — ReliefChain gives you
            the tools to deliver aid transparently and efficiently.
          </p>
          <button className="btn btn-primary" id="cta-join-btn" onClick={() => navigate('/funds')}>
            Get Started Now <ArrowRight size={18} />
          </button>
        </div>
      </section>

      {/* ── Footer ── */}
      <footer className="footer" id="about">
        <div className="footer-content">
          <span className="footer-text">
            © {new Date().getFullYear()} ReliefChain. Built with transparency in
            mind.
          </span>
          <ul className="footer-links">
            <li>
              <a href="#">Privacy</a>
            </li>
            <li>
              <a href="#">Terms</a>
            </li>
            <li>
              <a href="#">Documentation</a>
            </li>
            <li>
              <a href="#">GitHub</a>
            </li>
          </ul>
        </div>
      </footer>

      <div className="chat-widget">
        {chatOpen && (
          <section className="chat-panel" aria-label="ReliefChain AI chat">
            <header className="chat-header">
              <div>
                <strong>ReliefChain Assistant</strong>
                <span>Ask about relief operations</span>
              </div>
              <button
                type="button"
                className="chat-close"
                aria-label="Close chat"
                onClick={() => setChatOpen(false)}
              >
                <X size={18} />
              </button>
            </header>
            <div className="chat-messages" aria-live="polite">
              {chatMessages.length === 0 && (
                <p className="chat-empty">How can I help with disaster relief today?</p>
              )}
              {chatMessages.map((item, index) => (
                <p className={`chat-message ${item.role}`} key={`${item.role}-${index}`}>
                  {item.content}
                </p>
              ))}
              {chatLoading && <p className="chat-status">Thinking…</p>}
              {chatError && <p className="chat-error" role="alert">{chatError}</p>}
            </div>
            <form className="chat-form" onSubmit={sendChatMessage}>
              <input
                aria-label="Message the ReliefChain assistant"
                value={chatInput}
                onChange={event => setChatInput(event.target.value)}
                placeholder="Write a message..."
                disabled={chatLoading}
              />
              <button type="submit" aria-label="Send message" disabled={!chatInput.trim() || chatLoading}>
                <Send size={16} />
              </button>
            </form>
          </section>
        )}
        <button
          type="button"
          className="chat-launcher"
          aria-label={chatOpen ? 'Close chat' : 'Open chat'}
          aria-expanded={chatOpen}
          onClick={() => setChatOpen(open => !open)}
        >
          {chatOpen ? <X size={22} /> : <MessageCircle size={22} />}
        </button>
      </div>
    </>
  );
}