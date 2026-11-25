import { useRef } from 'react';
import { motion, useScroll, useTransform } from 'framer-motion';
import {
  Activity,
  ArrowRight,
  BookOpen,
  CheckCircle2,
  FileText,
  HeartPulse,
  MessageSquare,
  Pill,
  ShieldCheck,
  Stethoscope,
} from 'lucide-react';
import heroImg from '../assets/hero-clinic.jpg';

interface Props {
  onStart: () => void;
  onLogin: () => void;
}

const fadeUp = {
  hidden: { opacity: 0, y: 28 },
  show: (i: number = 0) => ({
    opacity: 1,
    y: 0,
    transition: { delay: i * 0.08, duration: 0.6, ease: [0.22, 1, 0.36, 1] as const },
  }),
};

const features = [
  {
    icon: <Stethoscope size={22} />,
    title: 'Guided symptom check',
    text: 'Six plain-language questions about your symptoms, severity and history. No medical jargon.',
  },
  {
    icon: <HeartPulse size={22} />,
    title: 'Urgency guidance',
    text: 'A transparent rule set returns High, Moderate or Low urgency, with the rule that triggered it.',
  },
  {
    icon: <FileText size={22} />,
    title: 'Shareable PDF report',
    text: 'Download a clean triage summary with your answers to bring to a doctor or nurse.',
  },
  {
    icon: <MessageSquare size={22} />,
    title: 'Health assistant chat',
    text: 'Ask medical questions and get structured, clear answers. Off-topic questions are declined.',
  },
  {
    icon: <Pill size={22} />,
    title: 'Know your medicine',
    text: 'Look up uses, common side effects, precautions and warnings for medicines and drugs.',
  },
  {
    icon: <BookOpen size={22} />,
    title: 'Medical dictionary',
    text: 'Plain-English definitions of clinical terms, with pronunciation and related words.',
  },
];

const steps = [
  { title: 'Describe what you feel', text: 'Pick your main symptom and rate its severity.' },
  { title: 'Answer a few questions', text: 'Duration, frequency, associated symptoms and age group.' },
  { title: 'Get your urgency level', text: 'See the result, the reason behind it and clear next steps.' },
];

export default function Landing({ onStart, onLogin }: Props) {
  const heroRef = useRef<HTMLDivElement>(null);
  const { scrollYProgress } = useScroll({ target: heroRef, offset: ['start start', 'end start'] });
  const imgY = useTransform(scrollYProgress, [0, 1], [0, 90]);

  return (
    <div>
      {/* Hero */}
      <section className="hero" ref={heroRef}>
        <div className="container hero-grid">
          <div>
            <motion.span className="eyebrow" variants={fadeUp} initial="hidden" animate="show" custom={0}>
              <ShieldCheck size={15} /> Safety-first health triage
            </motion.span>

            <motion.h1 variants={fadeUp} initial="hidden" animate="show" custom={1}>
              Know how urgently you need care,{' '}
              <span className="accent">in two minutes.</span>
            </motion.h1>

            <motion.p className="hero-sub" variants={fadeUp} initial="hidden" animate="show" custom={2}>
              Health-U turns your symptoms into a clear urgency level, using transparent clinical rules
              and an easy-to-read explanation. It helps you decide what to do next. It does not diagnose.
            </motion.p>

            <motion.div className="hero-cta" variants={fadeUp} initial="hidden" animate="show" custom={3}>
              <motion.button
                className="btn btn-primary btn-lg"
                onClick={onStart}
                whileHover={{ scale: 1.04 }}
                whileTap={{ scale: 0.97 }}
              >
                Start free <ArrowRight size={18} />
              </motion.button>
              <button className="btn btn-ghost btn-lg" onClick={onLogin}>
                I have an account
              </button>
            </motion.div>

            <motion.div className="hero-trust" variants={fadeUp} initial="hidden" animate="show" custom={4}>
              <div><strong>6</strong>guided questions</div>
              <div><strong>3</strong>urgency levels</div>
              <div><strong>PDF</strong>report in one click</div>
            </motion.div>
          </div>

          <motion.div
            className="hero-media"
            initial={{ opacity: 0, scale: 0.96 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ duration: 0.9, ease: [0.22, 1, 0.36, 1] }}
          >
            <motion.img style={{ y: imgY }} src={heroImg} alt="A doctor consulting with a patient" className="hero-photo" />

            <motion.div
              className="hero-float right"
              animate={{ y: [0, -8, 0] }}
              transition={{ duration: 4, repeat: Infinity, ease: 'easeInOut' }}
            >
              <span className="dot" style={{ background: 'var(--mod)' }} />
              <div>
                <strong>Moderate urgency</strong>
                <div style={{ color: 'var(--muted)' }}>See a clinician within 24h</div>
              </div>
            </motion.div>

            <motion.div
              className="hero-float left"
              animate={{ y: [0, 8, 0] }}
              transition={{ duration: 5, repeat: Infinity, ease: 'easeInOut' }}
            >
              <CheckCircle2 size={20} color="var(--low)" />
              <div>
                <strong>Rules explained</strong>
                <div style={{ color: 'var(--muted)' }}>Every result shows why</div>
              </div>
            </motion.div>
          </motion.div>
        </div>
      </section>

      {/* Features */}
      <section className="section" id="features">
        <div className="container">
          <motion.div
            className="section-head"
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, amount: 0.5 }}
            transition={{ duration: 0.6 }}
          >
            <span className="eyebrow"><Activity size={15} /> Everything in one place</span>
            <h2>Clear answers, not guesswork</h2>
            <p>Built around a visible rule set, so you can always see why a result was given.</p>
          </motion.div>

          <div className="feature-grid">
            {features.map((f, i) => (
              <motion.div
                key={f.title}
                className="feature"
                initial={{ opacity: 0, y: 30 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true, amount: 0.3 }}
                transition={{ delay: (i % 3) * 0.1, duration: 0.55, ease: [0.22, 1, 0.36, 1] }}
                whileHover={{ y: -4 }}
              >
                <div className="feature-icon">{f.icon}</div>
                <h3>{f.title}</h3>
                <p>{f.text}</p>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* How it works */}
      <section className="section" style={{ paddingTop: 20 }}>
        <div className="container">
          <div className="section-head">
            <span className="eyebrow">How it works</span>
            <h2>Three steps to clarity</h2>
          </div>
          <div className="steps">
            {steps.map((s, i) => (
              <motion.div
                key={s.title}
                className="step"
                initial={{ opacity: 0, x: -20 }}
                whileInView={{ opacity: 1, x: 0 }}
                viewport={{ once: true }}
                transition={{ delay: i * 0.12, duration: 0.5 }}
              >
                <div className="step-num">{i + 1}</div>
                <h3>{s.title}</h3>
                <p>{s.text}</p>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* Call to action band */}
      <section className="section" style={{ paddingTop: 20 }}>
        <div className="container">
          <motion.div
            className="band"
            initial={{ opacity: 0, y: 30 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, amount: 0.4 }}
            transition={{ duration: 0.7 }}
          >
            <div>
              <h2>Not sure if it's an emergency?</h2>
              <p>
                Health-U is a triage guide, not a replacement for a doctor. If you have chest pain,
                trouble breathing, stroke signs or severe bleeding, call your local emergency number now.
              </p>
              <div className="hero-cta" style={{ marginTop: 26 }}>
                <motion.button
                  className="btn btn-light btn-lg"
                  onClick={onStart}
                  whileHover={{ scale: 1.04 }}
                  whileTap={{ scale: 0.97 }}
                >
                  Check my symptoms
                </motion.button>
              </div>
            </div>
            <ul className="band-list">
              <li><CheckCircle2 size={18} /> Free to use</li>
              <li><CheckCircle2 size={18} /> No diagnosis or prescriptions</li>
              <li><CheckCircle2 size={18} /> Your results can be saved as a PDF</li>
              <li><CheckCircle2 size={18} /> Designed for triage, not treatment</li>
            </ul>
          </motion.div>
        </div>
      </section>

      <footer className="footer">
        <div className="container footer-inner">
          <div>© 2026 Health-U. Clinical decision support demonstration.</div>
          <div className="disclaimer-note">
            Not a diagnosis. In an emergency, call your local emergency number immediately.
          </div>
        </div>
      </footer>
    </div>
  );
}
