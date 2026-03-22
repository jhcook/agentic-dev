# Runbook Skeleton Specification

This document defines the structure and tagging conventions for Runbook Skeletons used by the Infrastructure Pipeline.

## Overview

A skeleton is a Markdown or YAML document decomposed into addressable blocks using HTML-style comments. This allows automated agents to inject content into specific segments while preserving the surrounding structure, styling, and whitespace.

## Block Tagging Convention

Blocks are defined using start and end markers. 

**Syntax**

```markdown
<!-- @block <ID> [metadata_key=value] -->
Content goes here.
<!-- @end -->
