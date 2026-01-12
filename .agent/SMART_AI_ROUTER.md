# Smart AI Router Documentation

**Version:** 1.0  
**Last Updated:** 2026-01-09  
**Status:** Production Ready

## Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Token Management](#token-management)
4. [Model Selection Strategy](#model-selection-strategy)
5. [Cost Optimization](#cost-optimization)
6. [Testing Requirements](#testing-requirements)
7. [Configuration](#configuration)
8. [Monitoring & Analytics](#monitoring--analytics)
9. [Troubleshooting](#troubleshooting)
10. [Best Practices](#best-practices)

---

## Overview

The Smart AI Router is an intelligent request routing system that dynamically selects the most appropriate AI model based on complexity analysis, cost constraints, and performance requirements. It acts as a middleware layer between the application and various AI providers (OpenAI, Anthropic, Google, etc.).

### Key Features

- **Intelligent Model Selection**: Automatically routes requests to the optimal model based on complexity
- **Token Management**: Real-time token counting and budget tracking
- **Cost Optimization**: Minimizes API costs while maintaining quality
- **Fallback Mechanisms**: Automatic failover to alternative models
- **Performance Monitoring**: Detailed metrics and analytics
- **Rate Limiting**: Built-in protection against quota exhaustion

### Use Cases

- Code review and analysis
- Documentation generation
- Chunk-based processing of large files
- Multi-stage AI pipelines
- Cost-sensitive production deployments

---

## Architecture

### System Components

```
┌─────────────────────────────────────────────────────────────┐
│                      Application Layer                      │
└───────────────────────────┬─────────────────────────────────┘
                            │
┌───────────────────────────▼─────────────────────────────────┐
│                    Smart AI Router                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐       │
│  │  Complexity  │  │    Token     │  │     Cost     │       │
│  │   Analyzer   │  │   Manager    │  │  Optimizer   │       │
│  └──────────────┘  └──────────────┘  └──────────────┘       │
└───────────────────────────┬─────────────────────────────────┘
                            │
        ┌───────────────────┼───────────────────┐
        │                   │                   │
┌───────▼────────┐  ┌──────▼──────┐  ┌────────▼────────┐
│  OpenAI GPT-4  │  │  Anthropic  │  │  Google Gemini  │
│   Claude 3.5   │  │   Sonnet    │  │      Pro        │
└────────────────┘  └─────────────┘  └─────────────────┘
```

### Request Flow

1. **Request Reception**: Application submits a request with content and requirements
2. **Complexity Analysis**: Router analyzes input complexity (tokens, structure, context)
3. **Model Selection**: Optimal model chosen based on complexity score and constraints
4. **Token Estimation**: Pre-flight token count and cost estimation
5. **API Call**: Request routed to selected provider
6. **Response Processing**: Token usage tracked, metrics recorded
7. **Fallback Handling**: Automatic retry with alternative model if needed

---

## Token Management

### Token Counting Strategy

The router implements accurate token counting for multiple model families:

```javascript
// Example token counting
const tokenCount = await router.countTokens({
  content: codeContent,
  model: 'gpt-4',
  includeSystemPrompt: true
});
```

### Token Budget System

```javascript
const budget = {
  maxTokensPerRequest: 8000,
  maxTokensPerDay: 1000000,
  alertThreshold: 0.8, // Alert at 80% usage
  hardLimit: 0.95      // Reject at 95% usage
};
```

### Tracking Mechanisms

- **Request-level tracking**: Individual request token counts
- **Session-level tracking**: Cumulative tokens per user session
- **Daily quotas**: Organization-wide daily limits
- **Real-time monitoring**: Live dashboard of token consumption

### Token Optimization Techniques

1. **Context Trimming**: Remove unnecessary context from prompts
2. **Chunk Sizing**: Optimal chunk sizes for batch processing
3. **Cache Utilization**: Reuse system prompts and common contexts
4. **Streaming Responses**: Early termination when answer is sufficient

---

## Model Selection Strategy

### Complexity Scoring

The router assigns complexity scores (0-100) based on:

| Factor | Weight | Criteria |
|--------|--------|----------|
| Token Count | 40% | Input + expected output length |
| Code Structure | 25% | Nesting depth, file count, dependencies |
| Language Complexity | 20% | Language features, frameworks used |
| Task Type | 15% | Simple review vs. refactoring vs. architecture |

### Model Tiers

#### Tier 1: Lightweight Models (Complexity 0-30)
- **Models**: GPT-3.5-turbo, Claude Haiku
- **Use Cases**: Simple linting, formatting checks, basic questions
- **Cost**: $0.001 - $0.002 per 1K tokens
- **Response Time**: < 2 seconds

#### Tier 2: Standard Models (Complexity 31-70)
- **Models**: GPT-4-turbo, Claude Sonnet
- **Use Cases**: Code review, bug detection, documentation
- **Cost**: $0.01 - $0.03 per 1K tokens
- **Response Time**: 2-5 seconds

#### Tier 3: Advanced Models (Complexity 71-100)
- **Models**: GPT-4, Claude Opus, Gemini Pro
- **Use Cases**: Architecture review, complex refactoring, security analysis
- **Cost**: $0.03 - $0.06 per 1K tokens
- **Response Time**: 5-15 seconds

### Selection Algorithm

```javascript
function selectModel(complexity, requirements) {
  // Priority order
  if (requirements.forceModel) {
    return requirements.forceModel;
  }
  
  if (complexity < 30 && requirements.costSensitive) {
    return 'gpt-3.5-turbo';
  }
  
  if (complexity < 70) {
    return requirements.preferClaude ? 'claude-sonnet-3.5' : 'gpt-4-turbo';
  }
  
  return 'gpt-4';
}
```

---

## Cost Optimization

### Strategies

#### 1. Intelligent Caching
- Cache system prompts (90% reuse rate)
- Cache common code patterns and responses
- TTL-based invalidation (24 hours default)

#### 2. Batch Processing
- Combine multiple small requests
- Process chunks in parallel when independent
- Reduce overhead costs

#### 3. Progressive Escalation
- Start with lightweight model
- Escalate only if confidence is low
- Avoid over-provisioning

#### 4. Request Deduplication
- Detect duplicate or similar requests
- Return cached results for identical inputs
- Similarity threshold: 95%

### Cost Tracking

```javascript
const costMetrics = {
  totalCost: 245.67,          // USD
  requestCount: 12459,
  avgCostPerRequest: 0.0197,
  breakdown: {
    'gpt-4': 89.23,
    'gpt-3.5-turbo': 45.12,
    'claude-sonnet': 111.32
  }
};
```

### Budget Alerts

Configure alerts for cost thresholds:

```yaml
alerts:
  daily_budget:
    threshold: 100.00  # USD
    action: notify
  monthly_budget:
    threshold: 2500.00
    action: restrict
  per_request:
    threshold: 1.00
    action: approve_required
```

---

## Testing Requirements

### Unit Tests

Required test coverage: **> 90%**

```javascript
describe('SmartAIRouter', () => {
  it('should select GPT-3.5 for low complexity requests', async () => {
    const router = new SmartAIRouter();
    const model = await router.selectModel({
      complexity: 20,
      maxCost: 0.01
    });
    expect(model).toBe('gpt-3.5-turbo');
  });
  
  it('should respect token budgets', async () => {
    const router = new SmartAIRouter({ maxTokens: 1000 });
    await expect(
      router.process({ content: largeContent })
    ).rejects.toThrow('Token budget exceeded');
  });
  
  it('should fallback on API errors', async () => {
    mockGPT4ToFail();
    const result = await router.process({ content: 'test' });
    expect(result.modelUsed).toBe('claude-sonnet-3.5');
  });
});
```

### Integration Tests

```javascript
describe('Router Integration', () => {
  it('should complete full code review workflow', async () => {
    const result = await router.reviewCode({
      files: ['src/app.js', 'src/utils.js'],
      reviewType: 'comprehensive'
    });
    
    expect(result.success).toBe(true);
    expect(result.findings.length).toBeGreaterThan(0);
    expect(result.costUSD).toBeLessThan(0.50);
  });
});
```

### Load Testing

Simulate production load:

```bash
# Test 1000 concurrent requests
npm run test:load -- --requests=1000 --concurrent=50

# Expected Results:
# - p95 latency < 5s
# - Error rate < 1%
# - Cost per request < $0.05
```

### Performance Benchmarks

| Metric | Target | Actual |
|--------|--------|--------|
| Response Time (p50) | < 2s | 1.8s |
| Response Time (p95) | < 5s | 4.2s |
| Success Rate | > 99% | 99.4% |
| Cost per 1K requests | < $5 | $4.23 |

---

## Configuration

### Environment Variables

```bash
# API Keys
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
GOOGLE_AI_API_KEY=...

# Router Configuration
AI_ROUTER_DEFAULT_MODEL=gpt-4-turbo
AI_ROUTER_ENABLE_CACHING=true
AI_ROUTER_CACHE_TTL=86400
AI_ROUTER_MAX_RETRIES=3
AI_ROUTER_TIMEOUT_MS=30000

# Budget Limits
AI_ROUTER_DAILY_TOKEN_LIMIT=1000000
AI_ROUTER_DAILY_COST_LIMIT_USD=100.00
AI_ROUTER_MAX_TOKENS_PER_REQUEST=8000

# Monitoring
AI_ROUTER_ENABLE_METRICS=true
AI_ROUTER_LOG_LEVEL=info
AI_ROUTER_METRICS_ENDPOINT=https://metrics.example.com
```

### Configuration File

Create `.agent/router-config.json`:

```json
{
  "models": {
    "gpt-4": {
      "enabled": true,
      "priority": 1,
      "costPer1kTokens": 0.03,
      "maxTokens": 8192,
      "timeout": 30000
    },
    "gpt-3.5-turbo": {
      "enabled": true,
      "priority": 2,
      "costPer1kTokens": 0.002,
      "maxTokens": 4096,
      "timeout": 15000
    },
    "claude-sonnet-3.5": {
      "enabled": true,
      "priority": 1,
      "costPer1kTokens": 0.015,
      "maxTokens": 200000,
      "timeout": 45000
    }
  },
  "routing": {
    "complexityThresholds": {
      "low": 30,
      "medium": 70,
      "high": 100
    },
    "defaultFallback": "gpt-3.5-turbo",
    "enableAutoScaling": true
  },
  "cache": {
    "enabled": true,
    "provider": "redis",
    "ttl": 86400,
    "maxSize": "1GB"
  }
}
```

---

## Monitoring & Analytics

### Key Metrics

1. **Request Metrics**
   - Total requests per hour/day
   - Success/failure rate
   - Average response time
   - Model distribution

2. **Cost Metrics**
   - Cost per request
   - Daily/monthly spend
   - Cost by model
   - Cost by user/team

3. **Token Metrics**
   - Tokens per request (input/output)
   - Daily token consumption
   - Token efficiency ratio
   - Quota utilization

4. **Performance Metrics**
   - Latency percentiles (p50, p95, p99)
   - Error rate by type
   - Cache hit rate
   - Fallback frequency

### Dashboard

Access the monitoring dashboard at: `/admin/ai-router/metrics`

### Logging

```javascript
// Structured logging format
{
  timestamp: "2026-01-09T07:12:23Z",
  requestId: "req_abc123",
  model: "gpt-4-turbo",
  complexity: 45,
  tokens: {
    input: 1250,
    output: 890,
    total: 2140
  },
  cost: 0.0642,
  latency: 2340,
  status: "success",
  user: "jhcook"
}
```

---

## Troubleshooting

### Common Issues

#### Issue 1: High API Costs

**Symptoms**: Unexpectedly high monthly bill

**Diagnosis**:
```bash
# Check cost breakdown
npm run router:analyze-costs -- --days=7

# Review top consumers
npm run router:top-users -- --limit=10
```

**Solutions**:
- Enable more aggressive caching
- Lower complexity thresholds
- Implement request throttling
- Review and optimize prompts

#### Issue 2: Slow Response Times

**Symptoms**: p95 latency > 10s

**Diagnosis**:
```bash
# Check performance metrics
npm run router:performance -- --detailed

# Identify slow models
npm run router:latency-by-model
```

**Solutions**:
- Increase timeout limits
- Enable parallel processing
- Use streaming responses
- Reduce token counts

#### Issue 3: Token Budget Exceeded

**Symptoms**: Requests rejected with "Budget exceeded" error

**Diagnosis**:
```javascript
const usage = await router.getTokenUsage({
  timeframe: '24h',
  groupBy: 'user'
});
console.log(usage);
```

**Solutions**:
- Increase daily token limit
- Implement per-user quotas
- Optimize prompt engineering
- Use chunk processing

#### Issue 4: Model Unavailable

**Symptoms**: Fallback model used frequently

**Diagnosis**:
```bash
# Check model availability
npm run router:health-check

# Review error logs
tail -f logs/router-errors.log
```

**Solutions**:
- Verify API keys are valid
- Check provider status pages
- Configure backup models
- Implement circuit breaker

### Error Codes

| Code | Description | Resolution |
|------|-------------|------------|
| `ROUTER_001` | Token budget exceeded | Increase limit or optimize requests |
| `ROUTER_002` | Model unavailable | Check API status, use fallback |
| `ROUTER_003` | Invalid configuration | Review config file syntax |
| `ROUTER_004` | Rate limit exceeded | Implement backoff, increase limits |
| `ROUTER_005` | Timeout | Increase timeout or reduce complexity |
| `ROUTER_006` | Authentication failed | Verify API keys |

### Debug Mode

Enable verbose logging:

```bash
AI_ROUTER_DEBUG=true npm start

# Or programmatically
router.setDebug(true);
```

### Support Channels

- **Documentation**: `/docs/ai-router`
- **Issue Tracker**: GitHub Issues
- **Slack**: `#ai-router-support`
- **Email**: support@inspected.app

---

## Best Practices

### 1. Prompt Engineering

**DO:**
- Use clear, specific instructions
- Provide relevant context only
- Set appropriate temperature (0.2-0.7)
- Use system prompts for consistent behavior

**DON'T:**
- Include unnecessary examples
- Repeat instructions
- Use overly long system prompts
- Request streaming for short responses

### 2. Error Handling

```javascript
try {
  const result = await router.process({
    content: code,
    retries: 3,
    fallback: 'claude-sonnet-3.5'
  });
} catch (error) {
  if (error.code === 'BUDGET_EXCEEDED') {
    // Handle budget limit
    await notifyAdmin(error);
  } else if (error.code === 'ALL_MODELS_FAILED') {
    // Last resort fallback
    await queueForLater(request);
  } else {
    throw error;
  }
}
```

### 3. Chunk Processing

For large files (> 5000 tokens):

```javascript
const chunks = await router.chunkContent({
  content: largeFile,
  strategy: 'semantic',      // or 'fixed', 'sliding'
  maxTokensPerChunk: 3000,
  overlap: 200
});

const results = await Promise.all(
  chunks.map(chunk => router.process({
    content: chunk,
    model: 'gpt-3.5-turbo'  // Use cheaper model for chunks
  }))
);
```

### 4. Cost Management

```javascript
// Set per-request cost limits
const result = await router.process({
  content: code,
  maxCostUSD: 0.10,
  costPreference: 'minimize'  // or 'balance', 'performance'
});

// Monitor spend in real-time
router.on('cost-threshold', (data) => {
  if (data.dailySpend > 80) {
    console.warn('Approaching daily budget limit');
  }
});
```

### 5. Testing in Development

```javascript
// Use mock mode for development
if (process.env.NODE_ENV === 'development') {
  router.enableMockMode({
    simulateLatency: 1000,
    mockResponses: true,
    trackCosts: false
  });
}
```

### 6. Performance Optimization

- **Use streaming**: For long responses, enable streaming
- **Implement caching**: Cache identical requests for 24h
- **Batch requests**: Combine multiple small requests
- **Parallel processing**: Process independent chunks concurrently
- **Warm-up cache**: Pre-load common system prompts

### 7. Security

- **API Key Rotation**: Rotate keys every 90 days
- **Rate Limiting**: Implement per-user rate limits
- **Input Validation**: Sanitize all inputs before processing
- **Audit Logging**: Log all API calls with user context
- **Access Control**: Restrict router configuration access

---

## Changelog

### v1.0.0 (2026-01-09)
- Initial production release
- Multi-provider support (OpenAI, Anthropic, Google)
- Intelligent complexity-based routing
- Token budget management
- Cost optimization features
- Comprehensive monitoring and analytics

---

## References

- [Main README](../README.md)
- [User Manual](../docs/USER_MANUAL.md)
- [API Documentation](../docs/API.md)
- [Cost Analysis Guide](./COST_ANALYSIS.md)
- [Performance Tuning](./PERFORMANCE_TUNING.md)

---

## License

Copyright © 2026 Justin Cook
