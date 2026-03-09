—
name: typescript-best-practices
description: Apply TypeScript best practices when writing, reviewing, or refactoring TypeScript code. Use this skill whenever the user asks to write TypeScript, review TS code, set up a project, fix type errors, or asks about types, interfaces, generics, tsconfig, enums, narrowing, utility types, type safety, or any TypeScript-specific question. Also trigger when the user shares a TypeScript file or snippet and asks for help — even if they don’t say “best practices” explicitly. If the task involves .ts or .tsx files, use this skill without hesitation.
—

# TypeScript Best Practices

Apply these rules whenever writing or reviewing TypeScript. The goal: make the type system do real work — catch bugs at compile time, document intent through types, and produce JavaScript that has no surprises at runtime.

Read reference files when you need depth:
- **`references/tsconfig.md`** — tsconfig options: strict tier, additional strictness flags, project-type presets
- **`references/patterns.md`** — type patterns: discriminated unions, generics, utility types, narrowing, `satisfies`, `as const`
- **`references/antipatterns.md`** — what to avoid: `any`, enums, `!`, `as`, index access holes, and their correct alternatives

—

## The Non-Negotiables

These apply to every TypeScript file, every time, with no exceptions.

### 1. `strict: true` in tsconfig — always

`strict` is not optional. It enables `strictNullChecks`, `noImplicitAny`, `strictFunctionTypes`, `useUnknownInCatchVariables`, and more. A codebase without it is just annotated JavaScript.

For new projects, also add:
```json
{
  “compilerOptions”: {
    “strict”: true,
    “noUncheckedIndexedAccess”: true,
    “noImplicitReturns”: true,
    “noFallthroughCasesInSwitch”: true,
    “noUnusedLocals”: true,
    “noUnusedParameters”: true
  }
}
```
See **`references/tsconfig.md`** for full presets by project type.

### 2. Never use `any`

`any` turns off type checking entirely. It is a bug vector, not a convenience.

```typescript
// ❌ Disables all safety
function process(data: any) { return data.name; }

// ✅ unknown forces you to narrow before using
function process(data: unknown) {
  if (typeof data === ‘object’ && data !== null && ‘name’ in data) {
    return (data as { name: string }).name;
  }
  throw new Error(‘Invalid data shape’);
}

// ✅ Or use a specific type / generic
function process<T extends { name: string }>(data: T) { return data.name; }
```

The only legitimate use of `any` is in declaration files for legacy JS, or when wrapping a third-party library with no types. Even then, wrap it immediately in a typed function.

### 3. Return types on exported functions

Let TypeScript infer local/private function return types, but annotate return types on all exported functions and public class methods. This creates a stable API contract that protects callers from accidental changes.

```typescript
// ✅ Explicit return type on public API
export function getUser(id: string): User | undefined { ... }
export async function fetchUsers(): Promise<User[]> { ... }

// ✅ Inferred is fine for internal/private functions
const formatName = (user: User) => `${user.first} ${user.last}`;
```

### 4. Narrow before accessing

Never assume. TypeScript’s control flow analysis is exact — give it the checks it needs.

```typescript
// ❌ Assumes value is present
function render(user?: User) { return user.name; }

// ✅ Guard first
function render(user?: User) {
  if (!user) return null;
  return user.name; // TypeScript now knows user is User
}
```

—

## Type Design

### Prefer `interface` for object shapes, `type` for everything else

```typescript
// ✅ interface — extensible, shows up as named in IDE errors
interface User {
  id: string;
  name: string;
  email: string;
}

// ✅ type — unions, intersections, mapped types, conditional types
type ID = string | number;
type AdminUser = User & { role: ‘admin’; permissions: string[] };
type MaybeUser = User | null;
type UserKeys = keyof User;
```

`interface` supports declaration merging (useful for module augmentation). Use it for shapes you want to be open to extension. Use `type` for everything that isn’t a plain object shape.

### Model state with discriminated unions

Discriminated unions are the single most powerful TypeScript pattern. Use them for any value that has a finite set of distinct states.

```typescript
// ❌ Boolean flags create impossible states
interface Request {
  isLoading: boolean;
  data?: User;
  error?: Error;    // can isLoading=true AND error be set simultaneously?
}

// ✅ Discriminated union — only valid states exist
type RequestState =
  | { status: ‘idle’ }
  | { status: ‘loading’ }
  | { status: ‘success’; data: User }
  | { status: ‘error’; error: Error };

function render(state: RequestState) {
  switch (state.status) {
    case ‘idle’:    return <Placeholder />;
    case ‘loading’: return <Spinner />;
    case ‘success’: return <View user={state.data} />;  // data is typed here
    case ‘error’:   return <Alert error={state.error} />; // error is typed here
  }
}
```

Always add an exhaustiveness check so adding a new variant causes a compile error at every unhandled switch:

```typescript
function assertNever(x: never): never {
  throw new Error(`Unhandled case: ${JSON.stringify(x)}`);
}

// In the default case of a switch over a discriminated union:
default: return assertNever(state); // compile error if any case is missing
```

### Use `as const` instead of enums

TypeScript enums have surprising runtime behavior (numeric enums generate reverse mappings; numeric enums accept any number; `const enum` breaks in `isolatedModules`). Prefer `as const` objects or union types.

```typescript
// ❌ enum — runtime object with quirks, not erasable
enum Direction { Up = ‘UP’, Down = ‘DOWN’, Left = ‘LEFT’, Right = ‘RIGHT’ }

// ✅ as const object — runtime object, no surprises, iterable
const Direction = { Up: ‘UP’, Down: ‘DOWN’, Left: ‘LEFT’, Right: ‘RIGHT’ } as const;
type Direction = typeof Direction[keyof typeof Direction]; // ‘UP’ | ‘DOWN’ | ‘LEFT’ | ‘RIGHT’

// ✅ Union type — type-only, zero runtime cost, easiest to use
type Direction = ‘UP’ | ‘DOWN’ | ‘LEFT’ | ‘RIGHT’;
```

**Decision rule:**
- Need runtime iteration/lookup? → `as const` object
- Type-only, small set? → union type
- Working with existing code or a class-oriented codebase? → string enum (with explicit string values only, never numeric)

### Compose types, don’t inherit them

```typescript
// ❌ Deep class inheritance — fragile, hard to test
class AdminUser extends User extends BaseEntity { ... }

// ✅ Compose interfaces
interface Timestamped { createdAt: Date; updatedAt: Date; }
interface Authored { authorId: string; }
type Post = { title: string; body: string } & Timestamped & Authored;
```

### Use `readonly` to prevent accidental mutation

```typescript
interface Config {
  readonly apiUrl: string;
  readonly timeout: number;
}

// For arrays:
function process(items: readonly string[]) { ... }  // can’t push/splice

// Utility type:
type ImmutableUser = Readonly<User>;
```

—

## Generics

Use generics to write code once that works for many types without sacrificing type safety.

```typescript
// ✅ Generic function — type flows through
function first<T>(arr: readonly T[]): T | undefined {
  return arr[0];
}
const n = first([1, 2, 3]);  // n is number | undefined
const s = first([‘a’, ‘b’]); // s is string | undefined

// ✅ Constrained generic — accept any object with an id field
function findById<T extends { id: string }>(items: T[], id: string): T | undefined {
  return items.find(item => item.id === id);
}
```

Add constraints with `extends` when you need to access properties. Default type parameters make generics easier to use:

```typescript
type ApiResponse<T = unknown> = {
  data: T;
  status: number;
  message: string;
};
```

—

## Utility Types — Use Them

Don’t repeat yourself with types. The built-in utility types exist so you don’t have to manually write mapped types for common operations.

| Utility | What it does | When to use |
|———|-————|-————|
| `Partial<T>` | All props optional | Update payloads, PATCH requests |
| `Required<T>` | All props required | After validation/defaults applied |
| `Readonly<T>` | All props readonly | Config objects, frozen state |
| `Pick<T, K>` | Select props | DTO slices, projections |
| `Omit<T, K>` | Exclude props | Create/Update types from full entity |
| `Record<K, V>` | Object with key type | Lookup maps, dictionaries |
| `Extract<T, U>` | Filter union members that extend U | Pull specific variants |
| `Exclude<T, U>` | Remove union members that extend U | Remove specific variants |
| `NonNullable<T>` | Remove null/undefined | After null guard |
| `ReturnType<F>` | Infer function return type | When you don’t own the function |
| `Parameters<F>` | Infer parameter tuple | Higher-order functions |
| `Awaited<T>` | Unwrap Promise | Async return types |

```typescript
// Common patterns
type CreateUserDto = Omit<User, ‘id’ | ‘createdAt’>;
type UpdateUserDto = Partial<Omit<User, ‘id’>>;
type UserSummary = Pick<User, ‘id’ | ‘name’ | ‘email’>;
type UserMap = Record<string, User>;
```

—

## Error Handling

```typescript
// ❌ catch gives unknown in strict mode — don’t assume Error
try { ... } catch (e) {
  console.error(e.message); // error: ‘e’ is unknown
}

// ✅ Narrow the catch variable
try { ... } catch (e) {
  if (e instanceof Error) {
    console.error(e.message);
  } else {
    console.error(String(e));
  }
}

// ✅ Or use a typed result pattern (no exceptions)
type Result<T, E = Error> =
  | { ok: true; value: T }
  | { ok: false; error: E };

async function fetchUser(id: string): Promise<Result<User>> {
  try {
    const user = await api.getUser(id);
    return { ok: true, value: user };
  } catch (e) {
    return { ok: false, error: e instanceof Error ? e : new Error(String(e)) };
  }
}
```

—

## What To Avoid (Quick Reference)

Full details in **`references/antipatterns.md`**.

| Antipattern | Problem | Fix |
|-————|———|——|
| `any` | Disables type checking | `unknown`, generics, specific types |
| Non-null assertion `!` | Hides null bugs | Guard with `if`, optional chaining |
| `as SomeType` | Lies to the compiler | Type guards, runtime validation |
| `enum` | Runtime quirks, not erasable | `as const` object or union type |
| Numeric `enum` | Accepts any number, reverse maps | String enum or union |
| Missing `strict` | Most bugs TypeScript can catch, won’t | Enable `strict: true` always |
| `index[i]` without guard | Undefined hole at runtime | Enable `noUncheckedIndexedAccess` |
| `// @ts-ignore` | Suppresses error without fixing it | `// @ts-expect-error` with a comment explaining why |

—

## Quick Decision Guide

**Interface vs type?** → Interface for object shapes; type for everything else.

**Generics vs overloads?** → Generics when the relationship between input/output types is parametric; overloads only when the signature genuinely varies by specific argument types.

**Optional `?` vs `| undefined`?** → `?` means the property may be absent; `prop: T | undefined` means present but possibly undefined. With `exactOptionalPropertyTypes` enabled, these are correctly distinct.

**`unknown` vs `any`?** → Always `unknown`. It forces narrowing. `any` skips narrowing entirely.

**Type assertion `as` vs type guard?** → Type guard always. `as` is a promise you make to the compiler that it can’t verify — if you’re wrong, the crash happens at runtime, silently.