import * as fs from 'node:fs';
import * as path from 'node:path';
import { describe, expect, test } from 'vitest';

import { CORE_RPC_METHODS, LEGACY_METHOD_ALIASES, normalizeRpcMethod } from '../rpcMethods';

describe('rpcMethods catalog', () => {
  describe('normalizeRpcMethod', () => {
    test('resolves all legacy aliases to their canonical core method', () => {
      for (const [legacyMethod, coreMethod] of Object.entries(LEGACY_METHOD_ALIASES)) {
        expect(normalizeRpcMethod(legacyMethod)).toBe(coreMethod);
      }
    });

    test('transforms auth methods by replacing dots with underscores', () => {
      expect(normalizeRpcMethod('eversilver.auth.login')).toBe('eversilver.auth_login');
      expect(normalizeRpcMethod('eversilver.auth.get.state')).toBe('eversilver.auth_get_state');
      expect(normalizeRpcMethod('eversilver.auth.a.b.c')).toBe('eversilver.auth_a_b_c');
    });

    test('transforms accessibility prefix to screen_intelligence prefix', () => {
      expect(normalizeRpcMethod('eversilver.accessibility_status')).toBe(
        'eversilver.screen_intelligence_status'
      );
      expect(normalizeRpcMethod('eversilver.accessibility_enable')).toBe(
        'eversilver.screen_intelligence_enable'
      );
    });

    test('returns unmapped or unrecognized methods unchanged', () => {
      expect(normalizeRpcMethod('eversilver.threads_list')).toBe('eversilver.threads_list');
      expect(normalizeRpcMethod('eversilver.unknown_method')).toBe('eversilver.unknown_method');
      expect(normalizeRpcMethod('')).toBe('');
      expect(normalizeRpcMethod('random_string')).toBe('random_string');
    });

    test('trims whitespace and converts to lower case', () => {
      expect(normalizeRpcMethod('  Eversilver.Auth.Login  ')).toBe('eversilver.auth_login');
      expect(normalizeRpcMethod('  EVERSILVER.GET_CONFIG ')).toBe(CORE_RPC_METHODS.configGet);
      expect(normalizeRpcMethod('Eversilver.Accessibility_Status  ')).toBe(
        'eversilver.screen_intelligence_status'
      );
      expect(normalizeRpcMethod('   some_RANDOM_method  ')).toBe('some_random_method');
    });
  });

  test('legacy aliases point at canonical method values', () => {
    expect(LEGACY_METHOD_ALIASES['eversilver.update_model_settings']).toBe(
      CORE_RPC_METHODS.configUpdateModelSettings
    );
    expect(LEGACY_METHOD_ALIASES['eversilver.workspace_onboarding_flag_set']).toBe(
      CORE_RPC_METHODS.configWorkspaceOnboardingFlagSet
    );
  });

  test('catalog canonical methods exist in core schema registry (drift guard)', () => {
    const schemaSources = [
      fs.readFileSync(
        path.resolve(__dirname, '../../../../src/eversilver/config/schemas.rs'),
        'utf8'
      ),
      fs.readFileSync(
        path.resolve(__dirname, '../../../../src/eversilver/screen_intelligence/schemas.rs'),
        'utf8'
      ),
      fs.readFileSync(
        path.resolve(__dirname, '../../../../src/eversilver/providers/schemas.rs'),
        'utf8'
      ),
    ].join('\n');

    for (const method of Object.values(CORE_RPC_METHODS)) {
      // core.* methods (e.g. core.ping) are special dispatch methods, not in the schema catalog.
      if (!method.startsWith('eversilver.')) continue;
      const methodRoot = method.slice('eversilver.'.length);
      const namespace = methodRoot.startsWith('screen_intelligence_')
        ? 'screen_intelligence'
        : methodRoot.startsWith('providers_')
          ? 'providers'
          : 'config';
      const fnName = methodRoot.slice(`${namespace}_`.length);
      expect(schemaSources).toContain(`namespace: "${namespace}"`);
      expect(schemaSources).toContain(`function: "${fnName}"`);
    }
  });
});
