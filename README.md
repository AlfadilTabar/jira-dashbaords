# Jira dashboards — Elasticsearch and Kibana 9.5.5

Seven Elasticsearch-only dashboards, with 85 metric panels and one alert-setup notice. No Prometheus server, collector, or additional running service is required. Original metric names, label names, expressions, dashboard titles, and panel placement are taken from the cloned Atlassian repository.

## Install

### Import directly

1. Extract the ZIP.
2. In Kibana, open **Stack Management → Saved Objects → Import**.
3. Select `jira-elastic-dashboards.ndjson`.
4. Open **Dashboards**, search **Jira |**, and select a dashboard.

The supplied NDJSON queries `jira*` with time field `@timestamp`. `Jira` is a data-view display name, not necessarily its underlying index pattern. If its index pattern differs, use the automatic installer below. It resolves the existing `Jira` data view; it does not create or modify data views.

### Automatically use your existing Jira data view

Run once from the extracted directory, using Python 3.10 or later:

```bash
export KIBANA_URL='https://your-kibana:5601'
export KIBANA_AUTH='ApiKey YOUR_ENCODED_API_KEY'
python3 install.py
```

`KIBANA_AUTH` is the complete Authorization header; Basic authentication is also supported. For a non-default space, include `/s/SPACE_ID` in `KIBANA_URL`. For a private CA, set `CA_CERT=/path/to/ca.pem`. TLS verification stays enabled.

The installer reads the data-view metadata, resolves its index pattern and time field, regenerates the dashboard file, and imports it. It never reads sample documents or transmits your data outside your deployment. It exits after import; nothing needs to keep running. Importing requires Kibana saved-object privileges; viewing requires read access to the metrics indices.

- `python3 install.py --prepare-only`: resolve the data view and generate the NDJSON, then import it manually.
- `python3 install.py --data-view EXACT_ID`: resolve duplicate display names by specifying the data-view ID.
- `python3 install.py --overwrite`: deliberately update this package's previously imported IDs. Omit to avoid overwriting edited dashboards.
- `python3 build.py --index 'your-index-*' --time-field '@timestamp'`: generate for a known index pattern without contacting Kibana.

## Included dashboards

General; Cache Clearing; Cluster Locks; Database Load; Indexing; Response Times; Tasks.

## Assumed data shape

Metric values are top-level numeric fields with the original names, such as `com_atlassian_jira_metrics_Count`, `com_atlassian_jira_metrics_Mean`, and `jvm_memory_bytes_used`. Labels are single-valued keyword fields with the original names, such as `instance`, `category00`, `name`, and `tag_invokerPluginKey`. The time field is a date. One document contains a metric sample or a set of metrics with the same labels and timestamp.

`expected-mapping.json` lists all 26 metric fields and the expected label fields. It is documentation; importing the dashboards does not apply or change mappings. The scripts read doc values; text-only fields, nested label objects, runtime fields defined only on the data view, and histogram-shaped metrics need adaptation. Standard extra labels `job` and `product` participate in series identity. If your data contains additional identifying labels not in expected-mapping.json, add those labels to build.py before regenerating; otherwise distinct series can be combined or rejected as conflicting samples.

## Calculations

The dashboards use Kibana Vega visualizations backed by Elasticsearch `scripted_metric` aggregations. The included compiler translates the specific expression subset used in the source: metric selectors, `sum/avg/max by/without`, `topk`, arithmetic, `time()`, `rate`, `increase`, and `delta`.

Weighted means retain per-series pairing before cluster aggregation. Counter `rate`/`increase` handle decreases as resets; `delta` intentionally preserves decreases. Range functions use the original five- or ten-minute windows and boundary extrapolation. Instant values use the latest sample within a five-minute lookback. Raw p99 metrics are used directly; they are not recomputed as percentiles of aggregated percentile values. Division by zero and nonfinite results are omitted.

This is a translation of the repository's expression subset, not a general PromQL engine. Results depend on the stored timestamps, complete labels, and available samples. Prometheus-specific stale-marker behavior is not represented in ordinary Elasticsearch documents.

## Display differences and limits

- Time-series panels remain time series. Stat/gauge panels become numeric rows. Table panels become scrollable text tables; each original query is a separate row, rather than the Grafana transformation joining several query outputs into columns. Hover for full series details. Row section headers, exact colors, thresholds, and Grafana formatting are not reproduced.
- Units are retained as source unit identifiers. Values stay in original units; numeric start times remain epoch values. No silent unit conversion is applied.
- Grafana alerts and alert history cannot be imported as Kibana rules by this package. The Recent Alerts panel contains an explicit notice.
- Default time range is one hour. Refresh is paused initially. Time-series evaluation has a minimum one-minute step and approximately 120 points; long time ranges are sampled more coarsely while original rolling windows remain fixed. Charts connect available points and do not add explicit Prometheus staleness markers.
- Each panel reads up to ten minutes before the selected range for rolling calculations. A snapshot is evaluated at the selected range's end. Dashboard KQL and filter pills are applied through Kibana's query placeholders.
- Each panel has an explicit limit of 100,000 intermediate metric samples and 20,000 output rows. Excess work fails with a clear message instead of silently truncating. Narrow the time range or filter by instance/plugin when needed. Scripted aggregations can be expensive on high-cardinality datasets; start with Last 15 minutes and load one dashboard at a time.
- Requires Elasticsearch Stack with scripted metric aggregations permitted. This aggregation is not available on Elasticsearch Serverless. No cluster settings or mappings are changed by the installer.

## Source inconsistencies retained

The source queries were not silently corrected:

- Cluster Locks panel 7, “Active Locks Waiting,” selects `held`; the waiting time-series panel selects `waited`.
- Database Load panel 38, SAL operation times, selects AO `executeInTransaction`.
- General CPU multiplies ProcessCpuLoad by 1000.
- Tomcat thread utilization uses currentThreadCount/maxThreads, not busy-thread count.
- Some source cluster-wide counts use `avg`, and several count-based weighted expressions use `delta` rather than reset-aware `increase`.

`conversion-manifest.json` preserves every converted expression for review.

## Validation

- All 85 Elasticsearch query bodies parsed with the actual Elasticsearch **9.5.5** SearchSourceBuilder/query parser, after replacing Kibana time/filter placeholders with concrete test values.
- Map and reduce scripts compiled using the actual Elasticsearch **9.5.5 Painless compiler** and scripted-metric contexts.
- Reduce scripts executed for all 85 metric panels using synthetic samples, plus four numerical assertions covering counter resets, rates, negative delta, and a weighted mean: **89 passing fixtures**.
- All 85 Vega definitions compiled and rendered to SVG with Vega 5 and synthetic data.
- All 93 saved objects passed JSON parsing, unique-ID, reference, and layout checks.
- Installer tested against a local mock Kibana API.

A full Elasticsearch daemon could not start under the workspace's restricted user mapping; tests used its real parser and Painless engine directly. No live Kibana 9.5.5 import or end-to-end test against your data was performed. The validation establishes component syntax and tested calculations, not deployment-specific field compatibility or load performance.

## Source and license

https://github.com/atlassian-labs/data-center-grafana-dashboards/tree/main/jira

Pinned source commit: `bc301d21050e12e4439b2c68c5b95ac588f7c632`.

Derived from Atlassian and others' Apache-2.0-licensed dashboard definitions. Originals are included under `source/`; `LICENSE.txt` is preserved. The generated dashboards and translation code are modified derivatives.

References:
- https://www.elastic.co/docs/explore-analyze/visualize/custom-visualizations-with-vega
- https://www.elastic.co/docs/reference/aggregations/search-aggregations-metrics-scripted-metric-aggregation
- https://www.elastic.co/docs/api/doc/kibana/operation/operation-post-saved-objects-import
- https://www.elastic.co/docs/api/doc/kibana/operation/operation-getalldataviewsdefault
