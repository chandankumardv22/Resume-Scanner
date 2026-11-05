import React, { useState } from 'react';
import { UserPlus, User, Mail, Lock, Phone, Eye, EyeOff, ArrowLeft } from 'lucide-react';
import { apiService, formatAuthError } from './api/client';

export default function RegisterPage({ onGoSignIn, onGoHome }) {
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [phone, setPhone] = useState('');
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
        phone: phone.trim(),
      });
      setInfo('Account created successfully! Redirecting to sign in…');
      setTimeout(() => onGoSignIn?.(), 1000);
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
                <UserPlus size={28} />
              </div>
              <span className="tw-section-label">Register</span>
              <h1 className="tw-auth-page__title">Create Account</h1>
              <p className="tw-auth-page__sub">
                Register with your name, email address, and password to get started.
              </p>

              {error && <div className="tw-auth-alert tw-auth-alert--error">{error}</div>}
              {info && <div className="tw-auth-alert tw-auth-alert--info">{info}</div>}

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
                      <span className="ms-1">{showPassword ? 'Hide' : 'Show'}</span>
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

                <label>
                  <Phone size={14} className="me-1" /> Phone number (optional)
                  <input
                    type="tel"
                    value={phone}
                    onChange={(e) => setPhone(e.target.value)}
                    placeholder="10-digit mobile"
                    autoComplete="tel"
                    disabled={loading}
                  />
                </label>

                <button type="submit" className="btn btn-primary tw-btn-primary w-100" disabled={loading}>
                  {loading ? 'Creating account…' : 'Create Account'}
                </button>
              </form>

              <p className="tw-auth-page__footer">
                Already registered?{' '}
                <button type="button" className="tw-auth-page__link" onClick={onGoSignIn}>
                  Sign in here
                </button>
              </p>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
