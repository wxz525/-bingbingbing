CREATE TABLE fund_archive (
  fund_code VARCHAR(32) NOT NULL,
  fund_name VARCHAR(128) NOT NULL,
  fund_type VARCHAR(32) NULL,
  manager_name VARCHAR(128) NULL,
  custodian_name VARCHAR(128) NULL,
  establish_date DATE NULL,
  currency CHAR(3) NULL,
  fund_status VARCHAR(16) NULL,
  etl_source_file VARCHAR(512) NULL,
  etl_batch_id VARCHAR(64) NULL,
  created_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  updated_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3)
    ON UPDATE CURRENT_TIMESTAMP(3),
  PRIMARY KEY (fund_code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='基金基础信息';

CREATE TABLE fund_redemption_rule (
  rule_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  fund_code VARCHAR(32) NOT NULL,
  version_no INT UNSIGNED NOT NULL,
  purchase_status VARCHAR(16) NULL,
  redeem_status VARCHAR(16) NULL,
  min_purchase_amount DECIMAL(18,2) NULL,
  min_additional_purchase_amount DECIMAL(18,2) NULL,
  daily_purchase_limit DECIMAL(18,2) NULL,
  min_redeem_shares DECIMAL(18,4) NULL,
  min_holding_shares DECIMAL(18,4) NULL,
  purchase_fee_rate DECIMAL(10,6) NULL,
  redeem_fee_rate DECIMAL(10,6) NULL,
  purchase_confirm_days SMALLINT UNSIGNED NULL,
  redeem_confirm_days SMALLINT UNSIGNED NULL,
  redeem_arrival_days SMALLINT UNSIGNED NULL,
  effective_date DATE NULL,
  remark VARCHAR(512) NULL,
  source_type VARCHAR(8) NOT NULL,
  etl_batch_id VARCHAR(64) NULL,
  is_deleted TINYINT(1) NOT NULL DEFAULT 0,
  active_fund_code VARCHAR(32)
    GENERATED ALWAYS AS (IF(is_deleted = 0, fund_code, NULL)) STORED,
  created_by VARCHAR(64) NOT NULL,
  created_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  deleted_by VARCHAR(64) NULL,
  deleted_at DATETIME(3) NULL,
  PRIMARY KEY (rule_id),
  UNIQUE KEY uk_fund_version (fund_code, version_no),
  UNIQUE KEY uk_active_source (active_fund_code, source_type),
  KEY idx_fund_history (fund_code, is_deleted, version_no),
  CONSTRAINT fk_rule_fund FOREIGN KEY (fund_code)
    REFERENCES fund_archive (fund_code) ON DELETE RESTRICT,
  CONSTRAINT chk_rule_source CHECK (source_type IN ('ETL', 'MANUAL')),
  CONSTRAINT chk_purchase_status CHECK (
    purchase_status IS NULL OR purchase_status IN ('OPEN', 'CLOSED', 'SUSPENDED')
  ),
  CONSTRAINT chk_redeem_status CHECK (
    redeem_status IS NULL OR redeem_status IN ('OPEN', 'CLOSED', 'SUSPENDED')
  ),
  CONSTRAINT chk_rule_amount CHECK (
    (min_purchase_amount IS NULL OR min_purchase_amount >= 0)
    AND (min_additional_purchase_amount IS NULL OR min_additional_purchase_amount >= 0)
    AND (daily_purchase_limit IS NULL OR daily_purchase_limit >= 0)
    AND (min_redeem_shares IS NULL OR min_redeem_shares >= 0)
    AND (min_holding_shares IS NULL OR min_holding_shares >= 0)
  ),
  CONSTRAINT chk_rule_fee CHECK (
    (purchase_fee_rate IS NULL OR purchase_fee_rate BETWEEN 0 AND 100)
    AND (redeem_fee_rate IS NULL OR redeem_fee_rate BETWEEN 0 AND 100)
  ),
  CONSTRAINT chk_rule_delete CHECK (
    (is_deleted = 0 AND deleted_at IS NULL AND deleted_by IS NULL)
    OR (is_deleted = 1 AND deleted_at IS NOT NULL AND deleted_by IS NOT NULL)
  )
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='基金申赎规则版本';
