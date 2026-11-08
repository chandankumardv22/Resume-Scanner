// ==============================================================================
// TECH STACK OVERVIEW - FRONTEND:
// - UI Framework: React 19 (Hooks, Concurrent Rendering)
// - Drag & Drop File Upload: react-dropzone
// - HTTP & API Client: Axios
// - Icon System: Lucide React
// - Client-Side PDF Generation: jsPDF + jspdf-autotable (via pdfReport module)
// - Styling & Layout: Vanilla CSS (Custom Design Tokens, Glassmorphism, Bootstrap Grid)
// ==============================================================================

// --- [TECH STACK: React 19] Core UI Library & Lifecycle Hooks ---
import React, { useState, useCallback, useMemo, useEffect, useRef } from 'react';

// --- [TECH STACK: react-dropzone] Drag-and-drop file upload engine ---
import { useDropzone } from 'react-dropzone';

// --- [TECH STACK: Axios] Centralized Production API Client ---
import { apiService, formatApiError, getApiOrigin } from './api/client';

// --- [TECH STACK: Lucide React] Clean, customizable SVG icons ---
import {
  Upload,
  FileSearch,
  FileText,
  Target,
  Briefcase,
  CheckCircle2,
  Loader2,
  Layers,
  Globe,
  Shield,
  Route,
  Zap,
  Mail,
  Phone,
  UserPlus,
  LogIn,
  LogOut,
  User,
} from 'lucide-react';

import LiveJobOpenings from './LiveJobOpenings';
import SignInPage from './SignInPage';
import RegisterPage from './RegisterPage';

// --- [TECH STACK: jsPDF & jspdf-autotable] Career Report Generator ---
import { generateCareerReportPdf } from './pdfReport';

// --- [TECH STACK: Custom CSS & Styling] ---
import './App.css';

const AUTH_STORAGE_KEY = 'ra_auth';

const FEATURE_ICONS = {
  target: Target,
  layers: Layers,
  briefcase: Briefcase,
  route: Route,
  globe: Globe,
  shield: Shield,
};

function useCountUp(target, duration = 1200) {
  const [value, setValue] = useState(0);
  const started = useRef(false);

  useEffect(() => {
    if (started.current || !target) return undefined;
    started.current = true;
    const start = performance.now();
    const tick = (now) => {
      const progress = Math.min((now - start) / duration, 1);
      const eased = 1 - (1 - progress) ** 3;
      setValue(Math.round(eased * target));
      if (progress < 1) requestAnimationFrame(tick);
    };
    requestAnimationFrame(tick);
    return undefined;
  }, [target, duration]);

  return value;
}

function BrandName({ variant = 'header' }) {
  return (
    <div className={`ra-brand ra-brand--${variant}`}>
      <span className="ra-brand__resume">Resume</span>
      <span className="ra-brand__analyzer">Analyzer</span>
    </div>
  );
}

function Navbar({ scrolled, user, onOpenAuth, onLogout, onGoHome }) {
  const scrollTo = (id) => {
    onGoHome?.();
    setTimeout(() => {
      document.getElementById(id)?.scrollIntoView({ behavior: 'smooth' });
    }, 50);
  };

  return (
    <nav className={`tw-navbar ${scrolled ? 'tw-navbar--scrolled' : ''}`}>
      <div className="container tw-navbar__inner">
        <div className="tw-brand" role="button" tabIndex={0} onClick={onGoHome} onKeyDown={(e) => e.key === 'Enter' && onGoHome?.()} style={{ cursor: 'pointer' }}>
          <div className="tw-brand__icon">RA</div>
          <BrandName variant="header" />
        </div>
        <div className="tw-nav">
          <a href="#home" onClick={(e) => { e.preventDefault(); scrollTo('home'); }}>Home</a>
          <a href="#services" onClick={(e) => { e.preventDefault(); scrollTo('services'); }}>Services</a>
          <a href="#upload" onClick={(e) => { e.preventDefault(); scrollTo('upload'); }}>Analyze</a>
          <a href="#process" onClick={(e) => { e.preventDefault(); scrollTo('process'); }}>Process</a>
          <a href="#listings" onClick={(e) => { e.preventDefault(); scrollTo('listings'); }}>Listings</a>
        </div>
        <div className="tw-navbar__actions">
          {user ? (
            <>
              <span className="tw-navbar__user" title={user.email || user.phone || user.name}>
                <User size={16} />
                {user.name}
              </span>
              <button type="button" className="tw-nav-icon-btn" onClick={onLogout} title="Sign out" aria-label="Sign out">
                <LogOut size={18} />
                <span>Sign out</span>
              </button>
            </>
          ) : (
            <>
              <button type="button" className="tw-nav-icon-btn" onClick={() => onOpenAuth('register')} title="Register" aria-label="Register">
                <UserPlus size={18} />
                <span>Register</span>
              </button>
              <button type="button" className="tw-nav-icon-btn" onClick={() => onOpenAuth('signin')} title="Sign in" aria-label="Sign in">
                <LogIn size={18} />
                <span>Sign in</span>
              </button>
            </>
          )}
          <button type="button" className="btn btn-primary tw-btn-primary btn-sm" onClick={() => scrollTo('upload')}>
            Get Started
          </button>
        </div>
      </div>
    </nav>
  );
}

function StatsBar({ stats }) {
  const analyses = useCountUp(stats?.total_analyses ?? 0);
  const domains = useCountUp(stats?.domains_supported ?? 8);
  const roles = useCountUp(stats?.job_roles_per_scan ?? 5);
  const jobsPerRole = stats?.jobs_per_role ?? 4;

  const items = [
    { value: analyses, label: 'Resumes Analyzed' },
    { value: domains, label: 'Career Domains' },
    { value: roles, label: 'Roles Per Scan' },
    { value: jobsPerRole, label: 'Listings Per Role' },
  ];

  return (
    <div className="tw-stats">
      {items.map((item) => (
        <article key={item.label} className="tw-stat">
          <div className="tw-stat__value">{item.value}{item.label === 'Listings Per Role' ? '' : '+'}</div>
          <div className="tw-stat__label">{item.label}</div>
        </article>
      ))}
    </div>
  );
}

function ServicesGrid({ features }) {
  return (
    <section id="services" className="tw-section tw-section--alt">
      <div className="container">
        <div className="tw-section-head text-center">
          <span className="tw-section-label">Our Services</span>
          <h2 className="tw-section-title">Professional Career Solutions</h2>
          <p className="tw-section-sub">
            Complete talent intelligence services — like a premium real estate agency, but for your career path
          </p>
        </div>
        <div className="row g-4">
          {(features || []).map((feat) => {
            const Icon = FEATURE_ICONS[feat.icon] || Zap;
            return (
              <div key={feat.id} className="col-md-6 col-lg-4">
                <article className="tw-service-card">
                  <div className="tw-service-card__icon">
                    <Icon size={24} strokeWidth={2} />
                  </div>
                  <h3>{feat.title}</h3>
                  <p>{feat.description}</p>
                </article>
              </div>
            );
          })}
        </div>
      </div>
    </section>
  );
}

function ProcessSteps({ step }) {
  const steps = [
    { id: 1, label: 'Upload Resume', icon: Upload },
    { id: 2, label: 'AI Deep Scan', icon: FileSearch },
    { id: 3, label: 'Career Report', icon: FileText },
  ];
  return (
    <section className="tw-section tw-section--after-upload" id="process">
      <div className="container">
        <div className="tw-section-head text-center">
          <span className="tw-section-label">Process</span>
          <h2 className="tw-section-title">Your Career Journey in 3 Steps</h2>
        </div>
        <div className="tw-process">
          {steps.map((s) => {
            const Icon = s.icon;
            const status = step > s.id ? 'done' : step === s.id ? 'active' : 'pending';
            return (
              <div key={s.id} className={`tw-process__step tw-process__step--${status}`}>
                <div className="tw-process__node">
                  {status === 'done' ? <CheckCircle2 size={24} /> : <Icon size={24} />}
                </div>
                <span className="tw-process__label">{s.label}</span>
              </div>
            );
          })}
        </div>
      </div>
    </section>
  );
}

function UploadSection({ file, setFile, loading, error, onAnalyze }) {
  const onDrop = useCallback((accepted) => {
    if (accepted?.[0]) setFile(accepted[0]);
  }, [setFile]);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: { 'application/pdf': ['.pdf'] },
    maxFiles: 1,
    multiple: false,
    disabled: loading,
  });

  return (
    <section className="tw-section tw-section--upload" id="upload">
      <div className="container">
        <div className="row justify-content-center">
          <div className="col-lg-8">
            <div className="tw-section-head text-center mb-4">
              <span className="tw-section-label">Resume Analyzer</span>
              <h2 className="tw-section-title">Upload Your Resume for Analysis</h2>
              <p className="tw-section-sub">PDF format only — get ATS score, skills, gaps, and live job listings</p>
            </div>
            <div
              {...getRootProps()}
              className={`tw-upload-box ${isDragActive ? 'tw-upload-box--active' : ''} ${file ? 'tw-upload-box--ready' : ''} ${loading ? 'tw-upload-box--disabled' : ''}`}
            >
              <input {...getInputProps()} />
              <div className="tw-upload-box__icon">
                <Upload size={32} strokeWidth={1.75} />
              </div>
              {file ? (
                <>
                  <p className="tw-upload-box__title">{file.name}</p>
                  <p className="tw-upload-box__meta">{(file.size / 1024).toFixed(1)} KB · ready for analysis</p>
                </>
              ) : (
                <>
                  <p className="tw-upload-box__title">
                    {isDragActive ? 'Release to upload' : 'Drag & drop your resume PDF here'}
                  </p>
                  <p className="tw-upload-box__meta">or click to browse files</p>
                </>
              )}
            </div>
            <button
              type="button"
              className="btn btn-primary tw-btn-primary w-100"
              onClick={onAnalyze}
              disabled={loading || !file}
            >
              {loading ? (
                <>
                  <Loader2 className="tw-loading__icon d-inline-block me-2" size={18} style={{ animation: 'tw-spin 0.9s linear infinite' }} />
                  Analyzing Resume…
                </>
              ) : (
                'Launch Career Analysis'
              )}
            </button>
            {error && <div className="tw-alert" role="alert">{error}</div>}
          </div>
        </div>
      </div>
    </section>
  );
}

function AtsScoreRing({ score }) {
  const radius = 58;
  const circ = 2 * Math.PI * radius;
  const offset = circ - (score / 100) * circ;
  const color = score >= 75 ? '#10b981' : score >= 50 ? '#f59e0b' : '#ef4444';
  const status = score >= 75 ? 'Excellent' : score >= 50 ? 'Good' : 'Needs Improvement';
  const statusClass = score >= 75 ? 'excellent' : score >= 50 ? 'good' : 'needs-work';

  return (
    <div className="tw-ats-score">
      <div className="tw-ats-score__head">
        <span>ATS Compatibility</span>
        <span className={`tw-ats-score__status tw-ats-score__status--${statusClass}`}>{status}</span>
      </div>
      <div className="tw-score">
        <svg viewBox="0 0 140 140" className="tw-score__svg" aria-label={`ATS score ${score} out of 100`}>
          <circle cx="70" cy="70" r={radius} className="tw-score__track" />
          <circle
            cx="70"
            cy="70"
            r={radius}
            className="tw-score__fill"
            style={{ strokeDasharray: circ, strokeDashoffset: offset, stroke: color }}
          />
        </svg>
        <div className="tw-score__label">
          <span className="tw-score__value" style={{ color }}>{score}</span>
          <span className="tw-score__outof">out of 100</span>
        </div>
      </div>
      <div className="tw-score__scale" aria-label="Score benchmark">
        <div className="tw-score__scale-track">
          <span className="tw-score__scale-low" />
          <span className="tw-score__scale-mid" />
          <span className="tw-score__scale-high" />
        </div>
        <div className="tw-score__scale-labels">
          <span>Needs work<br /><strong>0-49</strong></span>
          <span>Good<br /><strong>50-74</strong></span>
          <span>Excellent<br /><strong>75-100</strong></span>
        </div>
      </div>
    </div>
  );
}

function Footer() {
  const scrollTo = (id) => {
    document.getElementById(id)?.scrollIntoView({ behavior: 'smooth' });
  };

  return (
    <footer className="tw-footer">
      <div className="container">
        <div className="row g-4">
          <div className="col-lg-5">
            <BrandName variant="footer" />
            <p className="tw-footer__tag">Professional career intelligence — ATS scoring, skill mapping &amp; live India job listings</p>
          </div>
          <div className="col-6 col-lg-3">
            <h5>Quick Links</h5>
            <ul>
              <li><a href="#home" onClick={(e) => { e.preventDefault(); scrollTo('home'); }}>Home</a></li>
              <li><a href="#services" onClick={(e) => { e.preventDefault(); scrollTo('services'); }}>Services</a></li>
              <li><a href="#upload" onClick={(e) => { e.preventDefault(); scrollTo('upload'); }}>Analyze</a></li>
              <li><a href="#listings" onClick={(e) => { e.preventDefault(); scrollTo('listings'); }}>Listings</a></li>
            </ul>
          </div>
          <div className="col-6 col-lg-4">
            <h5>Contact</h5>
            <ul>
              <li>
                <Mail size={14} className="me-1" />
                <a href="mailto:spakash134@gmail.com">spakash134@gmail.com</a>
              </li>
              <li>
                <Phone size={14} className="me-1" />
                <a href="tel:+917483701130">+91 7483701130</a>
              </li>
            </ul>
          </div>
        </div>
        <div className="tw-footer__bottom">
          © {new Date().getFullYear()} Resume Analyzer · Career Intelligence Platform
        </div>
      </div>
    </footer>
  );
}

function AiCareerSuggestionsSection({ structuredSuggestions, careerSuggestions }) {
  const suggestions = useMemo(() => {
    if (Array.isArray(structuredSuggestions) && structuredSuggestions.length > 0) {
      return structuredSuggestions;
    }
    if (!careerSuggestions) return [];

    const lines = String(careerSuggestions).split('\n').map((l) => l.trim()).filter(Boolean);
    const result = [];
    let cur = null;
    lines.forEach((line) => {
      const isHeader = (line.startsWith('•') && line.includes(':') && !line.includes(' - ')) || line.startsWith('###') || line.startsWith('##');
      if (isHeader) {
        const title = line.replace(/^[•#*\s]+/, '').replace(/:$/, '').trim();
        cur = { title, points: [] };
        result.push(cur);
      } else if (cur) {
        const pt = line.replace(/^[•\-*>\s]+/, '').trim();
        if (pt) cur.points.push(pt);
      } else {
        const pt = line.replace(/^[•\-*>\s]+/, '').trim();
        if (pt) {
          cur = { title: 'Executive Career Guidance', points: [pt] };
          result.push(cur);
        }
      }
    });
    return result.length > 0 ? result : [{ title: 'Personalized AI Career Guidance', points: [String(careerSuggestions)] }];
  }, [structuredSuggestions, careerSuggestions]);

  const [activeTab, setActiveTab] = useState(0);

  if (!suggestions.length) return null;

  return (
    <div className="tw-ai-suggestions-card mb-4">
      <div className="tw-ai-suggestions-head">
        <div className="d-flex align-items-center gap-2">
          <div className="tw-ai-badge-icon">
            <Zap size={20} />
          </div>
          <div>
            <h3 className="tw-ai-title mb-0">AI Career Intelligence & Suggestions</h3>
            <p className="tw-ai-subtitle mb-0">Actionable advice calibrated to your resume content & target role</p>
          </div>
        </div>
        <span className="tw-ai-model-tag">
          <Zap size={12} /> AI Advisor
        </span>
      </div>

      <div className="tw-ai-tabs">
        {suggestions.map((item, idx) => (
          <button
            key={idx}
            type="button"
            className={`tw-ai-tab ${activeTab === idx ? 'tw-ai-tab--active' : ''}`}
            onClick={() => setActiveTab(idx)}
          >
            {item.title}
          </button>
        ))}
      </div>

      {suggestions[activeTab] && (
        <div className="tw-ai-tab-content">
          <div className="tw-ai-category-header">
            <h4>{suggestions[activeTab].title}</h4>
          </div>
          <ul className="tw-ai-points-list">
            {(suggestions[activeTab].points || []).map((pt, i) => (
              <li key={i} className="tw-ai-point-item">
                <CheckCircle2 size={16} className="tw-ai-point-icon" />
                <span>{pt}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

function App() {
  const [file, setFile] = useState(null);
  const [loading, setLoading] = useState(false);
  const [results, setResults] = useState(null);
  const [error, setError] = useState(null);
  const [platformStats, setPlatformStats] = useState(null);
  const [features, setFeatures] = useState([]);
  const [scrolled, setScrolled] = useState(false);
  const [loadingStep, setLoadingStep] = useState(0);
  const [authPage, setAuthPage] = useState(null);
  const [authUser, setAuthUser] = useState(null);
  const [authToken, setAuthToken] = useState(null);
  const [exploreJobsData, setExploreJobsData] = useState(null);
  const [selectedExploreRole, setSelectedExploreRole] = useState('Full Stack Developer');
  const [exploreLoading, setExploreLoading] = useState(false);

  const timelineStep = useMemo(() => {
    if (results) return 3;
    if (loading) return 2;
    if (file) return 2;
    return 1;
  }, [file, loading, results]);

  useEffect(() => {
    try {
      const raw = localStorage.getItem(AUTH_STORAGE_KEY);
      if (!raw) return;
      const saved = JSON.parse(raw);
      if (saved?.token && saved?.user) {
        setAuthToken(saved.token);
        setAuthUser(saved.user);
        apiService
          .getMe(saved.token)
          .then((r) => {
            if (r?.user) {
              setAuthUser(r.user);
              localStorage.setItem(
                AUTH_STORAGE_KEY,
                JSON.stringify({ token: saved.token, user: r.user }),
              );
            }
          })
          .catch(() => {
            localStorage.removeItem(AUTH_STORAGE_KEY);
            setAuthToken(null);
            setAuthUser(null);
          });
      }
    } catch {
      localStorage.removeItem(AUTH_STORAGE_KEY);
    }
  }, []);

  useEffect(() => {
    apiService.getPlatformStats().then((data) => setPlatformStats(data)).catch(() => {});
    apiService.getFeatures().then((data) => setFeatures(data?.features || [])).catch(() => {});
  }, []);

  useEffect(() => {
    setExploreLoading(true);
    apiService
      .exploreJobs(selectedExploreRole)
      .then((data) => setExploreJobsData(data))
      .catch(() => {})
      .finally(() => setExploreLoading(false));
  }, [selectedExploreRole]);

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 40);
    window.addEventListener('scroll', onScroll, { passive: true });
    return () => window.removeEventListener('scroll', onScroll);
  }, []);

  useEffect(() => {
    if (!loading) {
      setLoadingStep(0);
      return undefined;
    }
    const timers = [
      setTimeout(() => setLoadingStep(1), 800),
      setTimeout(() => setLoadingStep(2), 3000),
      setTimeout(() => setLoadingStep(3), 6000),
    ];
    return () => timers.forEach(clearTimeout);
  }, [loading]);

  const handleAuthSuccess = ({ token, user }) => {
    setAuthToken(token);
    setAuthUser(user);
    localStorage.setItem(AUTH_STORAGE_KEY, JSON.stringify({ token, user }));
    setAuthPage(null);
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  const handleLogout = async () => {
    try {
      if (authToken) {
        await apiService.logout(authToken);
      }
    } catch {
      /* ignore */
    }
    localStorage.removeItem(AUTH_STORAGE_KEY);
    setAuthToken(null);
    setAuthUser(null);
  };
  const handleAnalyze = async () => {
    if (!file) return;
    setLoading(true);
    setError(null);
    setResults(null);

    try {
      const data = await apiService.analyzeResume(file);

      if (data?.error) {
        setError(data.error);
        return;
      }

      setResults(data);
      apiService.getPlatformStats().then((stats) => setPlatformStats(stats)).catch(() => {});
      setTimeout(() => {
        document.getElementById('dashboard')?.scrollIntoView({ behavior: 'smooth' });
      }, 300);
    } catch (err) {
      setError(formatApiError(err));
    } finally {
      setLoading(false);
    }
  };

  const matched = results?.matched_skills ?? [];
  const missing = results?.missing_skills ?? [];
  const role = results?.predicted_role;
  const roadmap = results?.learning_roadmap ?? [];
  const careerSuggestions = results?.career_suggestions ?? results?.custom_suggestion ?? '';
  const structuredSuggestions = results?.structured_suggestions ?? [];
  const meta = results?.candidate_metadata ?? {};
  const candidateName = meta.candidate_name || results?.candidate_name || 'Not found';
  const candidateEmail = meta.candidate_email || results?.candidate_email || 'Not found';
  const candidatePhone = meta.candidate_phone || results?.candidate_phone || 'Not found';
  const candidateCollege = meta.candidate_college || results?.candidate_college || 'Not found';
  const detectedDomain = results?.detected_domain || 'Not specified';
  const recommendedRoles = results?.recommended_roles ?? [];
  const jobsByRole = results?.jobs_by_role ?? {};
  const jobsMessage = results?.jobs_message ?? null;
  const jobsCount = results?.jobs_count ?? 0;

  const generatePDFReport = () => {
    if (!results) return;
    generateCareerReportPdf({
      candidateName,
      candidateEmail,
      candidatePhone,
      candidateCollege,
      detectedDomain,
      role,
      recommendedRoles,
      atsScore: results.ats_score ?? 0,
      matched,
      missing,
      careerSuggestions,
      structuredSuggestions,
      roadmap,
      customRoadmap: results?.custom_roadmap ?? [],
      jobsByRole,
    });
  };

  const loadingSteps = ['Parsing PDF', 'Extracting Skills', 'Matching Roles', 'Fetching Listings'];

  return (
    <div className="tw-app">
      <Navbar
        scrolled={scrolled}
        user={authUser}
        onOpenAuth={(mode) => setAuthPage(mode)}
        onLogout={handleLogout}
        onGoHome={() => setAuthPage(null)}
      />

      {authPage === 'signin' && (
        <SignInPage
          onAuthSuccess={handleAuthSuccess}
          onGoRegister={() => setAuthPage('register')}
          onGoHome={() => setAuthPage(null)}
        />
      )}

      {authPage === 'register' && (
        <RegisterPage
          onGoSignIn={() => setAuthPage('signin')}
          onGoHome={() => setAuthPage(null)}
        />
      )}

      {!authPage && (
        <>
      <section className="tw-hero" id="home">
        <div className="container">
          <p className="tw-hero__breadcrumb">
            Home <span>/</span> Career Agency <span>/</span> Resume Analyzer
          </p>
          <BrandName variant="hero" />
          <h1 className="tw-hero__title">
            Find Your <em>Perfect Career Match</em>
          </h1>
          <p className="tw-hero__sub">
            Resume Analyzer delivers premium resume analysis, ATS scoring, skill mapping,
            and live India job listings — tailored exclusively from your uploaded resume.
          </p>
          <div className="tw-hero__actions">
            <button type="button" className="btn btn-primary tw-btn-primary" onClick={() => document.getElementById('upload')?.scrollIntoView({ behavior: 'smooth' })}>
              Analyze My Resume
            </button>
            <button type="button" className="btn tw-btn-outline" onClick={() => document.getElementById('services')?.scrollIntoView({ behavior: 'smooth' })}>
              Explore Services
            </button>
          </div>
        </div>
      </section>

      <div className="container">
        <div className="tw-hero-search">
          <StatsBar stats={platformStats} />
        </div>
      </div>

      <ServicesGrid features={features} />
      <UploadSection
        file={file}
        setFile={setFile}
        loading={loading}
        error={error}
        onAnalyze={handleAnalyze}
      />
      <ProcessSteps step={timelineStep} />

      {loading && (
        <div className="container">
          <div className="tw-loading" role="status" aria-live="polite">
            <Loader2 className="tw-loading__icon" size={36} />
            <p>Processing your resume…</p>
            <div className="tw-loading__steps">
              {loadingSteps.map((label, i) => (
                <span key={label} className={`tw-loading__step ${loadingStep >= i ? 'tw-loading__step--active' : ''}`}>
                  {loadingStep > i ? '✓ ' : ''}{label}
                </span>
              ))}
            </div>
          </div>
        </div>
      )}

      {results && (
        <section className="tw-section tw-section--alt" id="dashboard">
          <div className="container">
            <div className="tw-section-head text-center mb-4">
              <span className="tw-section-label">Analysis Report</span>
              <h2 className="tw-section-title">Your Career Profile</h2>
              <p className="tw-section-sub">Insights derived exclusively from your uploaded resume</p>
            </div>

            <div className="tw-dashboard">
              <div className="tw-dashboard__meta">
                {[
                  ['Candidate Name', candidateName],
                  ['Email', candidateEmail],
                  ['Phone', candidatePhone],
                  ['College', candidateCollege],
                  ['Domain', detectedDomain],
                  ['Target Role', role || 'N/A'],
                  ['Recommended Roles', recommendedRoles.length ? recommendedRoles.join(', ') : 'N/A'],
                ].map(([label, val]) => (
                  <div key={label} className="tw-dashboard__meta-item">
                    <strong>{label}</strong>
                    {label === 'Recommended Roles' && recommendedRoles.length > 0 ? (
                      <ul className="tw-role-list">
                        {recommendedRoles.map((recommendedRole, index) => (
                          <li key={`${recommendedRole}-${index}`}>{recommendedRole}</li>
                        ))}
                      </ul>
                    ) : (
                      val
                    )}
                  </div>
                ))}
              </div>

              <div className="tw-dashboard__grid">
                <div className="tw-card tw-card--center">
                  <AtsScoreRing score={results.ats_score ?? 0} />
                  <p className="tw-card__hint">
                    {results.ats_score >= 75
                      ? 'Strong alignment for your target role.'
                      : results.ats_score >= 50
                      ? 'Solid foundation with room to close skill gaps.'
                      : 'Prioritize missing keywords and clearer resume structure.'}
                  </p>
                </div>

                <div className="tw-card">
                  <h3>Matched Skills</h3>
                  <div className="tw-chips">
                    {matched.length > 0 ? matched.map((s, i) => (
                      <span className="tw-chip tw-chip--matched" key={i}>{s}</span>
                    )) : (
                      <span className="tw-list__empty">No professional skills detected.</span>
                    )}
                  </div>
                  <h3 className="tw-card__subtitle">Skill Gaps</h3>
                  <div className="tw-chips">
                    {missing.length > 0 ? missing.map((s, i) => (
                      <span className="tw-chip" key={i}>{s}</span>
                    )) : (
                      <span className="tw-list__empty">No major gaps detected.</span>
                    )}
                  </div>
                </div>
              </div>

              <AiCareerSuggestionsSection
                structuredSuggestions={structuredSuggestions}
                careerSuggestions={careerSuggestions}
              />

              <div className="text-center mb-4">
                <button type="button" className="btn btn-primary tw-btn-primary" onClick={generatePDFReport}>
                  Download Career Report (PDF)
                </button>
                <p className="text-muted mt-2 small">
                  Complete report including candidate profile, ATS score, skills breakdown, AI suggestions, learning roadmap, and live job links.
                </p>
              </div>

              <div id="listings">
                <LiveJobOpenings
                  recommendedRoles={recommendedRoles}
                  jobsByRole={jobsByRole}
                  jobsMessage={jobsMessage}
                  jobsCount={jobsCount}
                  loading={false}
                  title="Personalized Job Matches — For Your Profile"
                  subtitle="Verified India openings matching your evaluated resume skills & recommended roles"
                />
              </div>
            </div>
          </div>
        </section>
      )}

      {!results && (
        <section className="tw-section tw-section--alt" id="listings">
          <div className="container">
            <div className="d-flex flex-wrap justify-content-center gap-2 mb-4">
              {[
                'Full Stack Developer',
                'Data Analyst',
                'Cloud & DevOps Engineer',
                'Python Developer',
                'React Developer',
                'AI/ML Engineer',
                'UI/UX Designer',
                'Financial Analyst',
              ].map((roleName) => (
                <button
                  key={roleName}
                  type="button"
                  className={`btn btn-sm ${selectedExploreRole === roleName ? 'btn-primary tw-btn-primary' : 'btn-outline-secondary'}`}
                  onClick={() => setSelectedExploreRole(roleName)}
                >
                  {roleName}
                </button>
              ))}
            </div>
            <LiveJobOpenings
              recommendedRoles={exploreJobsData?.roles || [selectedExploreRole]}
              jobsByRole={exploreJobsData?.jobs_by_role || {}}
              jobsMessage={exploreJobsData?.jobs_message}
              jobsCount={exploreJobsData?.jobs_count || 0}
              loading={exploreLoading}
              title={`Live Openings for ${selectedExploreRole}`}
              subtitle="Browse real-time openings in India across top tech companies, startups & enterprises"
            />
          </div>
        </section>
      )}

      <Footer />
        </>
      )}
    </div>
  );
}

export default App;
