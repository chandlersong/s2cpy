ALTER DATABASE test SET timezone = 'UTC';
CREATE EXTENSION IF NOT EXISTS timescaledb;
DROP TABLE IF EXISTS polymarket_history CASCADE;

-- Table definition: note we DO NOT set a single-column primary key here because
-- TimescaleDB requires that any unique index / primary key include the
-- hypertable's time partitioning column. We'll add a composite primary key
-- (market_id, timestamp) after converting the table to a hypertable.
CREATE TABLE polymarket_history (
    id bigint,
    series_id TEXT,
    series_slug TEXT,
    event_id TEXT,
    event_slug TEXT,
    market_id TEXT NOT NULL,
    market_slug TEXT,
    asset_id TEXT,
    asset_slug TEXT,
    timestamp timestamptz NOT NULL,
    price DOUBLE PRECISION,
    batch_timestamp bigint
);

-- After converting to hypertable, add a primary key (or unique constraint)
-- that includes the time column. This avoids TS103 (unique constraint must
-- include partitioning column).
ALTER TABLE polymarket_history
  ADD CONSTRAINT polymarket_history_pkey PRIMARY KEY (market_id, timestamp);

-- Create hypertable on integer timestamp (epoch milliseconds).
-- Provide chunk_time_interval in the same units (ms). Example uses 7 days.
SELECT create_hypertable(
  'polymarket_history',
  'timestamp',
  if_not_exists => TRUE
);



-- Enable compression and set orderby/segmentby. timescaledb.compress must be assigned a value.
ALTER TABLE polymarket_history SET (
  timescaledb.enable_columnstore,
  timescaledb.orderby = 'timestamp DESC',
  timescaledb.segmentby = 'market_id'
);


SELECT add_compression_policy('polymarket_history', INTERVAL '30 days');
