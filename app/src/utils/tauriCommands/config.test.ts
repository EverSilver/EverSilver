import { isTauri } from '@tauri-apps/api/core';
import { afterEach, beforeEach, describe, expect, type Mock, test, vi } from 'vitest';

import { callCoreRpc } from '../../services/coreRpcClient';

vi.mock('@tauri-apps/api/core', () => ({ invoke: vi.fn(), isTauri: vi.fn() }));
vi.mock('../../services/coreRpcClient', () => ({ callCoreRpc: vi.fn() }));

describe('tauriCommands/config', () => {
  const mockIsTauri = isTauri as Mock;
  const mockCallCoreRpc = callCoreRpc as Mock;
  let eversilverUpdateLocalAiSettings: typeof import('./config').eversilverUpdateLocalAiSettings;
  let eversilverUpdateMeetSettings: typeof import('./config').eversilverUpdateMeetSettings;
  let eversilverGetMeetSettings: typeof import('./config').eversilverGetMeetSettings;

  beforeEach(async () => {
    vi.clearAllMocks();
    mockIsTauri.mockReturnValue(true);
    const actual = await vi.importActual<typeof import('./config')>('./config');
    eversilverUpdateLocalAiSettings = actual.eversilverUpdateLocalAiSettings;
    eversilverUpdateMeetSettings = actual.eversilverUpdateMeetSettings;
    eversilverGetMeetSettings = actual.eversilverGetMeetSettings;
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe('eversilverUpdateLocalAiSettings', () => {
    test('throws when not running in Tauri', async () => {
      mockIsTauri.mockReturnValue(false);
      await expect(eversilverUpdateLocalAiSettings({ runtime_enabled: true })).rejects.toThrow(
        'Not running in Tauri'
      );
      expect(mockCallCoreRpc).not.toHaveBeenCalled();
    });

    test('forwards the patch to eversilver.config_update_local_ai_settings', async () => {
      mockCallCoreRpc.mockResolvedValue({
        result: { config: {}, workspace_dir: '/tmp', config_path: '/tmp/cfg.toml' },
        logs: [],
      });
      const patch = {
        runtime_enabled: true,
        opt_in_confirmed: true,
        provider: 'lm_studio',
        base_url: 'http://localhost:1234/v1',
        model_id: 'local-model',
        chat_model_id: 'local-model',
        usage_embeddings: true,
        usage_subconscious: false,
      };
      await eversilverUpdateLocalAiSettings(patch);
      expect(mockCallCoreRpc).toHaveBeenCalledWith({
        method: 'eversilver.config_update_local_ai_settings',
        params: patch,
      });
    });
  });

  describe('eversilverUpdateMeetSettings (#1299)', () => {
    test('throws when not running in Tauri', async () => {
      mockIsTauri.mockReturnValue(false);
      await expect(
        eversilverUpdateMeetSettings({ auto_orchestrator_handoff: true })
      ).rejects.toThrow('Not running in Tauri');
      expect(mockCallCoreRpc).not.toHaveBeenCalled();
    });

    test('forwards the patch to eversilver.config_update_meet_settings', async () => {
      mockCallCoreRpc.mockResolvedValue({
        result: { config: {}, workspace_dir: '/tmp', config_path: '/tmp/cfg.toml' },
        logs: [],
      });
      await eversilverUpdateMeetSettings({ auto_orchestrator_handoff: true });
      expect(mockCallCoreRpc).toHaveBeenCalledWith({
        method: 'eversilver.config_update_meet_settings',
        params: { auto_orchestrator_handoff: true },
      });
    });
  });

  describe('eversilverGetMeetSettings (#1299)', () => {
    test('throws when not running in Tauri', async () => {
      mockIsTauri.mockReturnValue(false);
      await expect(eversilverGetMeetSettings()).rejects.toThrow('Not running in Tauri');
      expect(mockCallCoreRpc).not.toHaveBeenCalled();
    });

    test('reads via eversilver.config_get_meet_settings', async () => {
      mockCallCoreRpc.mockResolvedValue({ result: { auto_orchestrator_handoff: true }, logs: [] });
      const out = await eversilverGetMeetSettings();
      expect(mockCallCoreRpc).toHaveBeenCalledWith({
        method: 'eversilver.config_get_meet_settings',
      });
      expect(out.result.auto_orchestrator_handoff).toBe(true);
    });
  });

  describe('eversilverUpdateComposioTriggerSettings', () => {
    let eversilverUpdateComposioTriggerSettings: typeof import('./config').eversilverUpdateComposioTriggerSettings;

    beforeEach(async () => {
      const actual = await vi.importActual<typeof import('./config')>('./config');
      eversilverUpdateComposioTriggerSettings = actual.eversilverUpdateComposioTriggerSettings;
    });

    test('throws when not running in Tauri', async () => {
      mockIsTauri.mockReturnValue(false);
      await expect(
        eversilverUpdateComposioTriggerSettings({ triage_disabled: true })
      ).rejects.toThrow('Not running in Tauri');
      expect(mockCallCoreRpc).not.toHaveBeenCalled();
    });

    test('forwards the patch to eversilver.config_update_composio_trigger_settings', async () => {
      mockCallCoreRpc.mockResolvedValue({
        result: { config: {}, workspace_dir: '/tmp', config_path: '/tmp/cfg.toml' },
        logs: [],
      });
      const patch = { triage_disabled: true, triage_disabled_toolkits: ['gmail', 'slack'] };
      await eversilverUpdateComposioTriggerSettings(patch);
      expect(mockCallCoreRpc).toHaveBeenCalledWith({
        method: 'eversilver.config_update_composio_trigger_settings',
        params: patch,
      });
    });

    test('returns no-op on unknown method from stale core (#1597)', async () => {
      mockCallCoreRpc.mockRejectedValue(
        new Error('unknown method: eversilver.config_update_composio_trigger_settings')
      );
      const out = await eversilverUpdateComposioTriggerSettings({ triage_disabled: true });
      expect(out).toEqual({ result: { config: {}, workspace_dir: '', config_path: '' }, logs: [] });
    });

    test('rethrows non-unknown-method errors', async () => {
      mockCallCoreRpc.mockRejectedValue(new Error('network timeout'));
      await expect(
        eversilverUpdateComposioTriggerSettings({ triage_disabled: true })
      ).rejects.toThrow('network timeout');
    });
  });

  describe('eversilverGetComposioTriggerSettings', () => {
    let eversilverGetComposioTriggerSettings: typeof import('./config').eversilverGetComposioTriggerSettings;

    beforeEach(async () => {
      const actual = await vi.importActual<typeof import('./config')>('./config');
      eversilverGetComposioTriggerSettings = actual.eversilverGetComposioTriggerSettings;
    });

    test('throws when not running in Tauri', async () => {
      mockIsTauri.mockReturnValue(false);
      await expect(eversilverGetComposioTriggerSettings()).rejects.toThrow('Not running in Tauri');
      expect(mockCallCoreRpc).not.toHaveBeenCalled();
    });

    test('reads via eversilver.config_get_composio_trigger_settings', async () => {
      mockCallCoreRpc.mockResolvedValue({
        result: { triage_disabled: false, triage_disabled_toolkits: ['slack'] },
        logs: [],
      });
      const out = await eversilverGetComposioTriggerSettings();
      expect(mockCallCoreRpc).toHaveBeenCalledWith({
        method: 'eversilver.config_get_composio_trigger_settings',
      });
      expect(out.result.triage_disabled).toBe(false);
      expect(out.result.triage_disabled_toolkits).toEqual(['slack']);
    });

    test('returns defaults on unknown method from stale core (#1597)', async () => {
      mockCallCoreRpc.mockRejectedValue(
        new Error('unknown method: eversilver.config_get_composio_trigger_settings')
      );
      const out = await eversilverGetComposioTriggerSettings();
      expect(out.result.triage_disabled).toBe(false);
      expect(out.result.triage_disabled_toolkits).toEqual([]);
    });

    test('rethrows non-unknown-method errors', async () => {
      mockCallCoreRpc.mockRejectedValue(new Error('network timeout'));
      await expect(eversilverGetComposioTriggerSettings()).rejects.toThrow('network timeout');
    });
  });
});
