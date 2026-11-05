import {
  getApiBaseUrl,
  getApiOrigin,
  formatApiError,
  apiClient,
  DEFAULT_TIMEOUT_MS,
  ANALYZE_TIMEOUT_MS,
} from './client';

describe('Centralized API Client', () => {
  const originalEnv = process.env.REACT_APP_API_URL;

  afterEach(() => {
    process.env.REACT_APP_API_URL = originalEnv;
  });

  test('resolves default API base URL when env is empty or not set', () => {
    delete process.env.REACT_APP_API_URL;
    expect(getApiBaseUrl()).toBe('http://127.0.0.1:8000');
    expect(getApiOrigin()).toBe('http://127.0.0.1:8000');
  });

  test('reads and trims REACT_APP_API_URL when set', () => {
    process.env.REACT_APP_API_URL = 'https://api.resumeanalyzer.com///';
    expect(getApiBaseUrl()).toBe('https://api.resumeanalyzer.com');
  });

  test('configures default timeouts correctly', () => {
    expect(DEFAULT_TIMEOUT_MS).toBe(30000);
    expect(ANALYZE_TIMEOUT_MS).toBe(120000);
    expect(apiClient.defaults.timeout).toBe(30000);
  });

  test('formats timeout error', () => {
    const err = { code: 'ECONNABORTED', message: 'timeout of 30000ms exceeded' };
    const msg = formatApiError(err);
    expect(msg).toContain('timed out');
  });

  test('formats 413 payload too large error', () => {
    const err = { response: { status: 413, data: {} } };
    const msg = formatApiError(err);
    expect(msg).toContain('too large');
  });

  test('formats 401 unauthorized session expiry error', () => {
    const err = { response: { status: 401, data: {} } };
    const msg = formatApiError(err);
    expect(msg).toContain('session has expired');
  });

  test('formats array detail error from FastAPI Pydantic schema validation', () => {
    const err = {
      response: {
        status: 422,
        data: {
          detail: [{ msg: 'Missing required field' }, { msg: 'Must be a valid PDF' }],
        },
      },
    };
    expect(formatApiError(err)).toBe('Missing required field; Must be a valid PDF');
  });
});
