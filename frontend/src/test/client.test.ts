import { describe, it, expect, vi, beforeEach } from 'vitest';
import { authApi, analyzeApi, projectsApi, chatApi, apiKeysApi } from '../api/client';

const mockFetch = vi.fn();
vi.stubGlobal('fetch', mockFetch);

function mockResponse(data: any, status = 200) {
  return Promise.resolve({
    ok: status >= 200 && status < 300,
    status,
    json: () => Promise.resolve(data),
    headers: new Headers({ 'content-type': 'application/json' }),
  });
}

beforeEach(() => {
  mockFetch.mockReset();
  localStorage.clear();
});

describe('authApi', () => {
  it('login sends correct payload', async () => {
    mockFetch.mockReturnValue(mockResponse({
      access_token: 'tok', user_id: '1', name: 'U', email: 'u@e.com', plan: 'free',
    }));

    const res = await authApi.login('u@e.com', 'pass');
    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining('/api/v1/auth/login'),
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ email: 'u@e.com', password: 'pass' }),
      })
    );
    expect(res.access_token).toBe('tok');
  });

  it('register sends correct payload', async () => {
    mockFetch.mockReturnValue(mockResponse({
      access_token: 'tok', user_id: '1', name: 'N', email: 'n@e.com', plan: 'free',
    }, 201));

    await authApi.register('n@e.com', 'pass', 'N');
    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining('/api/v1/auth/register'),
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ email: 'n@e.com', password: 'pass', name: 'N' }),
      })
    );
  });
});

describe('analyzeApi', () => {
  it('list returns analyses', async () => {
    mockFetch.mockReturnValue(mockResponse([]));
    const res = await analyzeApi.list();
    expect(res).toEqual([]);
  });

  it('exportUrl builds correct URL', () => {
    const url = analyzeApi.exportUrl('abc-123', 'json');
    expect(url).toContain('/api/v1/analyze/abc-123/export?format=json');
  });

  it('streamUrl returns stream endpoint', () => {
    const url = analyzeApi.streamUrl();
    expect(url).toContain('/api/v1/analyze/stream');
  });
});

describe('projectsApi', () => {
  it('create sends correct payload', async () => {
    mockFetch.mockReturnValue(mockResponse({
      id: '1', name: 'P', tags: [], visibility: 'private', analysis_ids: [],
      created_at: '', updated_at: '',
    }, 201));

    await projectsApi.create({ name: 'P' });
    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining('/api/v1/projects'),
      expect.objectContaining({ method: 'POST' })
    );
  });
});

describe('chatApi', () => {
  it('send posts message content', async () => {
    mockFetch.mockReturnValue(mockResponse({
      response: 'Hello', follow_up_suggestions: [], conversation_length: 2,
    }));

    const res = await chatApi.send('analysis-1', 'Hello');
    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining('/api/v1/chat/analysis-1/send'),
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ content: 'Hello' }),
      })
    );
    expect(res.response).toBe('Hello');
  });
});

describe('apiKeysApi', () => {
  it('create sends name', async () => {
    mockFetch.mockReturnValue(mockResponse({
      id: '1', name: 'K', key_preview: 'mosaic_...', full_key: 'mosaic_abc',
      created_at: '', expires_at: null, last_used_at: null,
    }, 201));

    await apiKeysApi.create({ name: 'K' });
    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining('/api/v1/api-keys'),
      expect.objectContaining({ method: 'POST' })
    );
  });
});
