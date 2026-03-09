# tsconfig Reference

## What `strict: true` enables

`strict` is a bundle flag that turns on all of these simultaneously:

| Flag | What it catches |
|——|-—————|
| `strictNullChecks` | Forces you to handle `null` and `undefined` explicitly |
| `noImplicitAny` | Error when TypeScript infers `any` due to missing annotation |
| `strictFunctionTypes` | Stricter contravariant checking of function parameter types |
| `strictBindCallApply` | Checks `.call()`, `.bind()`, `.apply()` argument types |
| `strictPropertyInitialization` | Class properties must be initialized in constructor |
| `noImplicitThis` | Error when `this` would be inferred as `any` |
| `useUnknownInCatchVariables` | `catch (e)` variable is `unknown`, not `any` |
| `alwaysStrict` | Emits `”use strict”` in all output files |

**Never disable `strict`.** If it’s causing pain, the pain is pointing to real bugs. Fix the code, not the config.

—

## Flags not in `strict` — Enable These Too

These important flags are not included in `strict: true` and must be added manually:

### `noUncheckedIndexedAccess` ← Enable for all new projects

Without it, array indexing and object property access via bracket notation silently drop the `| undefined` that should be there:

```typescript
// noUncheckedIndexedAccess: false (TypeScript default — dangerous)
const ids: number[] = [];
const first = ids[0];      // TypeScript says: number
first.toFixed();            // ✅ TypeScript, 💥 runtime: Cannot read properties of undefined

// noUncheckedIndexedAccess: true (correct)
const first = ids[0];      // TypeScript says: number | undefined
first?.toFixed();           // must handle undefined
```

This also applies to `Record<string, T>` access:
```typescript
const map: Record<string, User> = {};
const user = map[‘unknown-key’]; // number | undefined — with the flag
```

### `noImplicitReturns`

Errors when a function doesn’t return on all code paths:
```typescript
// ❌ TypeScript won’t catch this without the flag
function getLabel(status: string): string {
  if (status === ‘active’) return ‘Active’;
  // silently returns undefined — runtime bug
}
```

### `noFallthroughCasesInSwitch`

Errors when a switch case falls through without `break`, `return`, or `throw`.

### `noUnusedLocals` / `noUnusedParameters`

Catches dead code and accidentally forgotten variables. Use `_` prefix to intentionally ignore a parameter:
```typescript
function handler(_event: Event, data: Data) { ... } // _event intentionally unused
```

### `exactOptionalPropertyTypes`

Makes `?` mean “may be absent” — not “may be absent or explicitly undefined”. These become distinct:
```typescript
interface Theme {
  colorScheme?: ‘light’ | ‘dark’;   // may be absent
}
// Without the flag, setting colorScheme: undefined is allowed
// With the flag, it’s an error — absent and undefined are different things
```

### `verbatimModuleSyntax` (TS 5.0+)

Ensures `import type` is used for type-only imports, which is required for some bundlers and enables better tree-shaking:
```typescript
import type { User } from ‘./types’;  // erased at compile time
import { UserService } from ‘./service’; // kept in output
```

—

## Recommended Presets by Project Type

### New Application (Node.js, React, Next.js)
```json
{
  “compilerOptions”: {
    “target”: “es2022”,
    “lib”: [“es2022”],
    “module”: “nodenext”,
    “moduleResolution”: “nodenext”,
    “strict”: true,
    “noUncheckedIndexedAccess”: true,
    “noImplicitReturns”: true,
    “noFallthroughCasesInSwitch”: true,
    “noUnusedLocals”: true,
    “noUnusedParameters”: true,
    “exactOptionalPropertyTypes”: true,
    “verbatimModuleSyntax”: true,
    “isolatedModules”: true,
    “moduleDetection”: “force”,
    “skipLibCheck”: true,
    “esModuleInterop”: true,
    “resolveJsonModule”: true,
    “outDir”: “./dist”,
    “rootDir”: “./src”,
    “sourceMap”: true
  },
  “include”: [“src/**/*”],
  “exclude”: [“node_modules”, “dist”]
}
```

### DOM / Browser App (add to above)
```json
{
  “compilerOptions”: {
    “lib”: [“es2022”, “dom”, “dom.iterable”],
    “jsx”: “react-jsx”
  }
}
```

### Library Package (publishable npm)
```json
{
  “compilerOptions”: {
    “declaration”: true,
    “declarationMap”: true,
    “composite”: true,
    “stripInternal”: true
  }
}
```

### Monorepo Base `tsconfig.base.json`
```json
{
  “compilerOptions”: {
    “strict”: true,
    “noUncheckedIndexedAccess”: true,
    “noImplicitReturns”: true,
    “skipLibCheck”: true,
    “esModuleInterop”: true,
    “target”: “es2022”,
    “moduleDetection”: “force”,
    “isolatedModules”: true
  }
}
```

Each package extends the base and adds its own `outDir`, `rootDir`, `references`, etc.

### Using Babel/SWC (not `tsc`) to transpile
```json
{
  “compilerOptions”: {
    “noEmit”: true,
    “module”: “preserve”,
    “isolatedModules”: true
  }
}
```

`isolatedModules: true` catches patterns that work with `tsc` but break with single-file transpilers (like re-exporting a type without `export type`).

—

## ESLint + typescript-eslint

tsconfig alone doesn’t catch everything. Pair it with `typescript-eslint` for complete coverage:

```bash
npm install -D @typescript-eslint/parser @typescript-eslint/eslint-plugin
```

Recommended flat config (`eslint.config.js`):
```javascript
import tseslint from ‘typescript-eslint’;

export default tseslint.config(
  ...tseslint.configs.strictTypeChecked,
  ...tseslint.configs.stylisticTypeChecked,
  {
    languageOptions: {
      parserOptions: { project: true },
    },
    rules: {
      ‘@typescript-eslint/no-explicit-any’: ‘error’,
      ‘@typescript-eslint/no-non-null-assertion’: ‘error’,
      ‘@typescript-eslint/explicit-function-return-type’: [‘error’, {
        allowExpressions: true,
        allowHigherOrderFunctions: true,
      }],
    },
  }
);
```

Key rules that tsconfig can’t enforce: `no-explicit-any`, `no-non-null-assertion`, `consistent-type-imports`, `no-floating-promises`.