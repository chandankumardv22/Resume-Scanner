import React, { useState } from 'react';
import { LogIn, Mail, Lock, Eye, EyeOff, ArrowLeft } from 'lucide-react';
import { apiService, formatAuthError } from './api/client';

export default function SignInPage({ onAuthSuccess, onGoRegister, onGoHome }) {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [info, setInfo] = useState('');

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
      setInfo('Signed in successfully! Redirecting…');
      onAuthSuccess?.({ token: data.token, user: data.user });
    } catch (err) {
      setError(formatAuthError(err));
    } finally {
      setLoading(false);
    }
  };

  return (
    <section className="tw-auth-page">
      <div className="container">
        <div className="row justify-content-center">
          <div className="col-lg-5 col-md-7">
            <button type="button" className="tw-auth-page__back" onClick={onGoHome}>
              <ArrowLeft size={16} /> Back to Home
            </button>

            <div className="tw-auth-page__card">
              <div className="tw-auth-page__icon">
                <LogIn size={28} />
              </div>
              <span className="tw-section-label">Sign In</span>
              <h1 className="tw-auth-page__title">Welcome Back</h1>
              <p className="tw-auth-page__sub">
                Sign in with your email address and password to access Resume Analyzer.
              </p>

              {error && <div className="tw-auth-alert tw-auth-alert--error">{error}</div>}
              {info && <div className="tw-auth-alert tw-auth-alert--info">{info}</div>}

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
                      <span className="ms-1">{showPassword ? 'Hide' : 'Show'}</span>
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

              <p className="tw-auth-page__footer">
                Don&apos;t have an account?{' '}
                <button type="button" className="tw-auth-page__link" onClick={onGoRegister}>
                  Register here
                </button>
              </p>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
