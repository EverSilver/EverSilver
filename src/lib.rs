//! Core library for the Eversilver platform.
//!
//! This crate provides the central logic for the Eversilver core binary, including:
//! - API and RPC handlers for external interactions.
//! - Core system services (CLI, configuration, monitoring).
//! - Domain-specific logic for the Eversilver agent runtime.

pub mod api;
pub mod core;
pub mod eversilver;
pub mod rpc;

pub use eversilver::config::DaemonConfig;
pub use eversilver::memory::{MemoryClient, MemoryState};

/// Runs the core logic based on the provided command-line arguments.
///
/// This is the primary entry point for the Eversilver binary, delegating to the
/// CLI module for argument parsing and command dispatch.
///
/// # Arguments
///
/// * `args` - A slice of strings containing the command-line arguments.
///
/// # Errors
///
/// Returns an error if command execution fails.
pub fn run_core_from_args(args: &[String]) -> anyhow::Result<()> {
    eversilver::service::apply_startup_restart_delay_from_env();
    core::cli::run_from_cli_args(args)
}
