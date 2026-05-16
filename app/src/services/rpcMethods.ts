export const CORE_RPC_METHODS = {
  configGet: 'eversilver.config_get',
  configGetAnalyticsSettings: 'eversilver.config_get_analytics_settings',
  configGetComposioTriggerSettings: 'eversilver.config_get_composio_trigger_settings',
  configGetRuntimeFlags: 'eversilver.config_get_runtime_flags',
  configSetBrowserAllowAll: 'eversilver.config_set_browser_allow_all',
  configUpdateAnalyticsSettings: 'eversilver.config_update_analytics_settings',
  configUpdateBrowserSettings: 'eversilver.config_update_browser_settings',
  configUpdateComposioTriggerSettings: 'eversilver.config_update_composio_trigger_settings',
  configUpdateLocalAiSettings: 'eversilver.config_update_local_ai_settings',
  configUpdateMemorySettings: 'eversilver.config_update_memory_settings',
  configUpdateModelSettings: 'eversilver.config_update_model_settings',
  configUpdateRuntimeSettings: 'eversilver.config_update_runtime_settings',
  configUpdateScreenIntelligenceSettings: 'eversilver.config_update_screen_intelligence_settings',
  configWorkspaceOnboardingFlagExists: 'eversilver.config_workspace_onboarding_flag_exists',
  configWorkspaceOnboardingFlagSet: 'eversilver.config_workspace_onboarding_flag_set',
  corePing: 'core.ping',
  providersListModels: 'eversilver.providers_list_models',
  screenIntelligenceStatus: 'eversilver.screen_intelligence_status',
} as const;

export type CoreRpcMethod = (typeof CORE_RPC_METHODS)[keyof typeof CORE_RPC_METHODS];

export const LEGACY_METHOD_ALIASES: Record<string, CoreRpcMethod> = {
  'eversilver.get_analytics_settings': CORE_RPC_METHODS.configGetAnalyticsSettings,
  'eversilver.get_composio_trigger_settings': CORE_RPC_METHODS.configGetComposioTriggerSettings,
  'eversilver.get_config': CORE_RPC_METHODS.configGet,
  'eversilver.get_runtime_flags': CORE_RPC_METHODS.configGetRuntimeFlags,
  'eversilver.ping': CORE_RPC_METHODS.corePing,
  'eversilver.set_browser_allow_all': CORE_RPC_METHODS.configSetBrowserAllowAll,
  'eversilver.update_analytics_settings': CORE_RPC_METHODS.configUpdateAnalyticsSettings,
  'eversilver.update_browser_settings': CORE_RPC_METHODS.configUpdateBrowserSettings,
  'eversilver.update_composio_trigger_settings':
    CORE_RPC_METHODS.configUpdateComposioTriggerSettings,
  'eversilver.update_local_ai_settings': CORE_RPC_METHODS.configUpdateLocalAiSettings,
  'eversilver.update_memory_settings': CORE_RPC_METHODS.configUpdateMemorySettings,
  'eversilver.update_model_settings': CORE_RPC_METHODS.configUpdateModelSettings,
  'eversilver.update_runtime_settings': CORE_RPC_METHODS.configUpdateRuntimeSettings,
  'eversilver.update_screen_intelligence_settings':
    CORE_RPC_METHODS.configUpdateScreenIntelligenceSettings,
  'eversilver.workspace_onboarding_flag_exists':
    CORE_RPC_METHODS.configWorkspaceOnboardingFlagExists,
  'eversilver.workspace_onboarding_flag_set': CORE_RPC_METHODS.configWorkspaceOnboardingFlagSet,
};

export function normalizeRpcMethod(method: string): string {
  const normalized = method.trim().toLowerCase();

  if (normalized in LEGACY_METHOD_ALIASES) {
    return LEGACY_METHOD_ALIASES[normalized];
  }

  if (normalized.startsWith('eversilver.auth.')) {
    return `eversilver.auth_${normalized.slice('eversilver.auth.'.length).split('.').join('_')}`;
  }

  if (normalized.startsWith('eversilver.accessibility_')) {
    return normalized.replace('eversilver.accessibility_', 'eversilver.screen_intelligence_');
  }

  return normalized;
}
