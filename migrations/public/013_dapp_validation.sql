-- DApp validation columns
-- Migration 013: add validation_status and validation_errors to dapp_builds

ALTER TABLE dapp_builds ADD COLUMN validation_status TEXT;
ALTER TABLE dapp_builds ADD COLUMN validation_errors TEXT;
