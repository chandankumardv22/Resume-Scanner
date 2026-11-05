import React, { useState } from 'react';
import { X, UserPlus, LogIn, Mail, Lock, User, Eye, EyeOff } from 'lucide-react';
import { apiService, formatAuthError } from './api/client';

export default function AuthModal({ mode, onClose, onAuthSuccess }) {
  const [tab, setTab] = useState(mode === 'register' ? 'register' : 'signin');
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [info, setInfo] = useState('');

  const handleRegister = async (e) => {
    e.preventDefault();
    setError('');
    setInfo('');

    if (!name.trim()) {
      setError('Please enter your full name.');
      return;
    }
    if (!email.trim()) {
      setError('Please enter your email address.');
      return;
    }
    if (!password || password.length < 6) {
      setError('Password must be at least 6 characters.');
      return;
    }

    setLoading(true);
    try {
      await apiService.register({
        name: name.trim(),
        email: email.trim(),
        password,
      });
      setInfo('Account created! Please sign in with your email and password.');
      setTab('signin');
      setPassword('');
    } catch (err) {
      setError(formatAuthError(err));
    } finally {
      setLoading(false);
    }
  };

  const handleSignIn = async (e) => {
    e.preventDefault();
    setError('');
    setInfo('');

    if (!email.trim()) {
      setError('Please enter your email address.');
      return;
    }
    if (!password) {
      setError('Please enter your password.');
      return;
    }

    setLoading(true);
    try {
      const data = await apiService.login({
        email: email.trim(),
        password,
      });
      onAuthSuccess?.({ token: data.token, user: data.user });
      onClose?.();
    } catch (err) {
      setError(formatAuthError(err));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="tw-auth-overlay" role="dialog" aria-modal="true" onClick={onClose}>
      <div className="tw-auth-modal" onClick={(e) => e.stopPropagation()}>
        <button type="button" className="tw-auth-modal__close" onClick={onClose} aria-label="Close">
          <X size={18} />
        </button>

        <div className="tw-auth-tabs">
          <button
            type="button"
            className={`tw-auth-tab ${tab === 'register' ? 'tw-auth-tab--active' : ''}`}
            onClick={() => { setTab('register'); setError(''); setInfo(''); }}
          >
            <UserPlus size={16} /> Register
          </button>
          <button
            type="button"
            className={`tw-auth-tab ${tab === 'signin' ? 'tw-auth-tab--active' : ''}`}
            onClick={() => { setTab('signin'); setError(''); setInfo(''); }}
          >
            <LogIn size={16} /> Sign In
          </button>
        </div>

        {error && <div className="tw-auth-alert tw-auth-alert--error">{error}</div>}
        {info && <div className="tw-auth-alert tw-auth-alert--info">{info}</div>}

        {tab === 'register' ? (
          <form onSubmit={handleRegister} className="tw-auth-form">
            <label>
              <User size={14} className="me-1" /> Full name
              <input
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="Your name"
                required
                minLength={2}
                autoComplete="name"
                disabled={loading}
              />
            </label>
            <label>
              <Mail size={14} className="me-1" /> Email Address
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@example.com"
                required
                autoComplete="email"
                disabled={loading}
              />
            </label>
            <label>
              <div className="d-flex justify-content-between align-items-center">
                <span>
                  <Lock size={14} className="me-1" /> Password
                </span>
                <button
                  type="button"
                  className="tw-auth-toggle-pwd"
                  onClick={() => setShowPassword(!showPassword)}
                  tabIndex={-1}
                  title={showPassword ? 'Hide password' : 'Show password'}
                >
                  {showPassword ? <EyeOff size={14} /> : <Eye size={14} />}
                </button>
              </div>
              <input
                type={showPassword ? 'text' : 'password'}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="Min 6 characters"
                required
                minLength={6}
                autoComplete="new-password"
                disabled={loading}
              />
            </label>
            <button type="submit" className="btn btn-primary tw-btn-primary w-100" disabled={loading}>
              {loading ? 'Creating account…' : 'Create Account'}
            </button>
          </form>
        ) : (
          <form onSubmit={handleSignIn} className="tw-auth-form">
            <label>
              <Mail size={14} className="me-1" /> Email Address
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@example.com"
                required
                autoComplete="email"
                disabled={loading}
              />
            </label>
            <label>
              <div className="d-flex justify-content-between align-items-center">
                <span>
                  <Lock size={14} className="me-1" /> Password
                </span>
                <button
                  type="button"
                  className="tw-auth-toggle-pwd"
                  onClick={() => setShowPassword(!showPassword)}
                  tabIndex={-1}
                  title={showPassword ? 'Hide password' : 'Show password'}
                >
                  {showPassword ? <EyeOff size={14} /> : <Eye size={14} />}
                </button>
              </div>
              <input
                type={showPassword ? 'text' : 'password'}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                required
                autoComplete="current-password"
                disabled={loading}
              />
            </label>
            <button type="submit" className="btn btn-primary tw-btn-primary w-100" disabled={loading}>
              {loading ? 'Signing in…' : 'Sign In'}
            </button>
          </form>
        )}
      </div>
    </div>
  );
}
