# Chunks Inventory

## Overview

This document tracks the historical chunks archive for the cybernetics-engine project.

Expected chunks: 001-128 (127 total chunks + 1 rebuilt version)

### Chunk Files Structure

All chunk files are stored in `historical/chunks-001-128/` directory and follow the naming convention:

```
cybernetics-engine-v1-chunk<NUMBER>.zip
cybernetics-engine-v1-chunk<NUMBER>-rebuilt.zip  (for rebuilt versions)
```

### Expected Chunks

#### Core Chunks (001-120)
- chunk001 through chunk120: Core application chunks
- Each chunk contains versioned components from the project history

#### Extended Chunks (121-128)
- chunk121 through chunk128: Extended components and additions
- chunk108-rebuilt: Rebuilt version of chunk 108

### Format

Each .zip file contains:
- Source code components
- Documentation
- Configuration files
- Test data

### Usage

Extract all chunks into `historical/chunks-001-128/`:

```bash
cd historical/chunks-001-128/
unzip "*.zip"
```

### Archival Policy

- ✅ Keep original .zip files for version control
- ✅ Extract only when needed for reference
- ✅ Do not modify contents
- ✅ Use for historical tracking and regression testing

### Inventory Status

**Last Updated:** 2026-09-09

| Range | Status | Count |
|-------|--------|-------|
| 001-050 | Pending | 50 |
| 051-100 | Pending | 50 |
| 101-120 | Ready | 20 |
| 121-128 | Ready | 8 |
| **Total** | **Pending** | **128** |

---

*Note: This inventory will be updated as chunks are added to the repository.*
