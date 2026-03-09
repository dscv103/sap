# Antipatterns — What to Avoid and Why

## Table of Contents
- [`any` — the root of all TypeScript evil](#any)
- [Non-null assertion `!` — hiding the bug](#non-null-assertion)
- [Type assertions `as` — lying to the compiler](#type-assertions-as)
- [Enums — runtime quirks and erasability](#enums)
- [Missing `strict`](#missing-strict)
- [Index access without guards](#index-access-without-guards)
- [`// @ts-ignore` vs `// @ts-expect-error`](#ts-ignore-vs-ts-expect-error)
- [Overusing `type` for object shapes](#overusing-type-for-object-shapes)
- [Mutating state directly](#mutating-state-directly)
- [Using `object` or `{}` as a type](#using-object-or—as-a-type)
- [Implicit function return `any`](#implicit-function-return-any)
- [Not handling Promise rejections](#not-handling-promise-rejections)

—

## `any`

`any` is an escape hatch from TypeScript’s type system. Using it means “I give up — don’t check this.” Every `any` is a potential runtime crash that the compiler can’t warn you about.

```typescript
// ❌ any disables all checking downstream
function process(data: any) {
  return data.nonExistentMethod(); // no error at compile time — crash at runtime
}

// ❌ any spreads: once a value is any, everything it touches becomes any
const result = process(userData); // result is also any
result.map(x => x.name);         // no error, but result might not be an array
```

**Fix decision tree:**
1. Do you know the exact shape? → Use that type or interface.
2. Is the shape variable but constrained? → Use a generic with `extends`.
3. Do you need to accept literally anything and figure it out? → Use `unknown` and narrow.
4. Is it from a third-party library with no types? → Write a typed wrapper function. Use `any` only inside the wrapper, never let it escape.

```typescript
// ✅ unknown — safe escape hatch that forces you to narrow
function process(data: unknown) {
  if (typeof data !== ‘object’ || data === null) throw new Error(‘Expected object’);
  if (!(‘name’ in data)) throw new Error(‘Expected name property’);
  return (data as { name: string }).name;
}

// ✅ Generic — type flows through safely
function first<T>(arr: T[]): T | undefined { return arr[0]; }
```

—

## Non-null assertion `!`

The `!` operator tells TypeScript “trust me, this isn’t null or undefined.” When you’re wrong, you get a runtime crash with no warning.

```typescript
// ❌ Dangerous: assumes the element always exists
const button = document.getElementById(‘submit’)!;
button.addEventListener(‘click’, handler); // crash if element doesn’t exist

// ❌ In a chain — hides multiple possible nulls
const name = user!.profile!.name!;
```

**The only legitimate use** of `!` is in tests (where you control the environment) or when you’ve already checked nullability nearby and TypeScript’s control flow analysis is missing context (rare).

```typescript
// ✅ Guard explicitly — clear, maintainable, self-documenting
const button = document.getElementById(‘submit’);
if (!button) throw new Error(‘Submit button not found in DOM’);
button.addEventListener(‘click’, handler);

// ✅ Optional chaining + nullish coalescing for safe access
const name = user?.profile?.name ?? ‘Anonymous’;
```

—

## Type assertions `as`

`as SomeType` is a compile-time lie. You’re telling TypeScript to treat a value as a specific type without any runtime verification. If you’re wrong, the crash happens silently later.

```typescript
// ❌ Assumes the API always returns a User
const user = await fetch(‘/api/user’).then(r => r.json()) as User;
user.name.toUpperCase(); // crash if the API returned an error object instead

// ❌ Double assertion — a red flag that you’re coercing incompatible types
const value = someValue as unknown as SpecificType; // “unknown” in the middle is the giveaway
```

**When `as` is actually OK:**
- Converting between known-compatible DOM types: `e.target as HTMLInputElement` (you know from context what element type it is)
- After you’ve already validated the shape with a type guard
- In a runtime validator implementation (like writing your own Zod)

```typescript
// ✅ Type guard validates before asserting
function isUser(value: unknown): value is User {
  return typeof value === ‘object’ && value !== null && ‘name’ in value;
}
const data: unknown = await fetch(‘/api/user’).then(r => r.json());
if (!isUser(data)) throw new Error(‘Invalid user response’);
data.name.toUpperCase(); // safe — TypeScript narrowed it
```

—

## Enums

TypeScript `enum` is the only TypeScript-specific syntax that emits JavaScript. This violates the principle that “removing TypeScript types from valid TS code produces valid JS code.” It also has surprising runtime behavior:

**Numeric enum problems:**
```typescript
enum Status { Active, Inactive } // inferred as 0, 1

// Numeric enums accept ANY number — no safety
function setStatus(s: Status) { ... }
setStatus(42);          // ✅ TypeScript allows this — NOT what you intended
setStatus(Status.Active); // ✅

// Numeric enums generate reverse mappings:
console.log(Status[0]); // ‘Active’  — unexpected
console.log(Object.keys(Status)); // [‘Active’, ‘Inactive’, ‘0’, ‘1’] — 6 keys total
```

**`const enum` problems:**
- Breaks with `isolatedModules: true` (required by most bundlers)
- Breaks when consumed across package boundaries
- Not supported by Babel, SWC, or esbuild

**Correct alternatives:**

```typescript
// ✅ Union type — zero runtime cost, purely a compile-time concept
type Status = ‘active’ | ‘inactive’ | ‘pending’;

// ✅ as const object — runtime object, no surprises, iterable, zero quirks
const STATUS = {
  Active:   ‘active’,
  Inactive: ‘inactive’,
  Pending:  ‘pending’,
} as const;
type Status = typeof STATUS[keyof typeof STATUS]; // ‘active’ | ‘inactive’ | ‘pending’

// Using the as const approach with iteration:
const validStatuses = Object.values(STATUS); // [‘active’, ‘inactive’, ‘pending’]
function isStatus(s: string): s is Status {
  return (validStatuses as string[]).includes(s);
}
```

**Exception:** String enums (with explicit string values) in a class-oriented codebase are acceptable, but add no benefit over `as const`. Numeric enums are almost always wrong.

—

## Missing `strict`

Without `strict: true`, TypeScript allows:

```typescript
// ❌ Without strictNullChecks — null/undefined accepted everywhere
let name: string = null;   // allowed
let user: User = undefined; // allowed — crash when you access user.name

// ❌ Without noImplicitAny — TypeScript silently infers any
function process(data) {   // data is any — no error
  return data.map(x => x.name); // no errors on nonexistent properties
}

// ❌ Without useUnknownInCatchVariables
try { ... } catch (e) {
  console.error(e.message); // allowed — but e could be anything thrown
}
```

**Never argue for disabling strict.** If strict causes pain, it’s finding real bugs. Fix the code.

—

## Index access without guards

Array and object index access silently returns `undefined` for missing keys, but TypeScript (without `noUncheckedIndexedAccess`) won’t tell you:

```typescript
// ❌ TypeScript says items[0] is Item — but what if items is empty?
function processFirst(items: Item[]): string {
  return items[0].name; // runtime crash if items is []
}

// ❌ Record access — TypeScript lies about the return type
const cache: Record<string, User> = {};
const user = cache[‘missing-key’];
user.name; // crash — user is actually undefined
```

```typescript
// ✅ Enable noUncheckedIndexedAccess in tsconfig — forces you to handle undefined
// Then TypeScript correctly says items[0] is Item | undefined
function processFirst(items: Item[]): string | undefined {
  return items[0]?.name;
}

// ✅ Guard explicitly even without the flag
function processFirst(items: Item[]): string {
  if (items.length === 0) throw new Error(‘Expected at least one item’);
  return items[0].name; // now guaranteed
}

// ✅ Use find/at/findIndex instead of raw index access
const first = items.at(0);          // Item | undefined — always explicit
const found = items.find(isTarget); // Item | undefined — always explicit
```

—

## `@ts-ignore` vs `@ts-expect-error`

`@ts-ignore` suppresses any TypeScript error on the next line, regardless of whether an error actually exists. It can silently mask bugs if the error it was suppressing gets fixed.

```typescript
// ❌ @ts-ignore — suppresses without verification
// @ts-ignore
const value = badValue.property; // if this error gets fixed, @ts-ignore hides it silently

// ✅ @ts-expect-error — MUST have an error on the next line, or TS errors
// @ts-expect-error: TODO: third-party library types are wrong, see issue #123
const value = thirdPartyLib.method();
```

`@ts-expect-error` is self-documenting: it tells you WHY the suppression exists, and it will error when the underlying issue is fixed, reminding you to clean it up.

**Rule:** Always use `@ts-expect-error` with a comment. Never use `@ts-ignore`.

—

## Overusing `type` for object shapes

`type` aliases for object shapes work fine, but `interface` is preferred because:
- It shows up with its name in IDE error messages (not as an expanded object)
- It supports declaration merging (needed for module augmentation, global types)
- `interface extends` is slightly more performant for the compiler than `&` intersection

```typescript
// ❌ type for a plain object shape — works but misses benefits
type User = { id: string; name: string };
type AdminUser = User & { permissions: string[] }; // intersection

// ✅ interface for object shapes
interface User { id: string; name: string; }
interface AdminUser extends User { permissions: string[]; }
```

Reserve `type` for: unions, intersections, mapped types, conditional types, template literal types, and aliases for primitives.

—

## Mutating state directly

Immutable patterns are safer and easier to type correctly:

```typescript
// ❌ Mutating — hard to track changes, breaks referential equality checks
function addUser(users: User[], user: User) {
  users.push(user); // mutates the original array
}

// ✅ Return new values
function addUser(users: readonly User[], user: User): User[] {
  return [...users, user];
}

// ❌ Mutating object properties
function activateUser(user: User) {
  user.status = ‘active’;
}

// ✅ Return new object
function activateUser(user: User): User {
  return { ...user, status: ‘active’ };
}
```

Use `readonly` on parameters to prevent mutations at the type level:
```typescript
function process(config: Readonly<Config>) { ... }
function transform(items: readonly Item[]) { ... }
```

—

## Using `object` or `{}` as a type

```typescript
// ❌ object — accepts any non-primitive, but you can’t access any properties
function log(data: object) {
  data.name; // error — ‘name’ doesn’t exist on type ‘object’
}

// ❌ {} — in TypeScript, this means “anything that’s not null or undefined”
//         (NOT an empty object — this is a common misunderstanding)
function log(data: {}) {
  // accepts strings, numbers, arrays — not useful as a constraint
}
```

```typescript
// ✅ Use specific types
function log(data: User | Post | Comment) { ... }

// ✅ Use a generic with a constraint
function log<T extends Record<string, unknown>>(data: T) { ... }

// ✅ If you genuinely need “any non-null value”, say so explicitly
function isDefined<T>(value: T | null | undefined): value is T {
  return value !== null && value !== undefined;
}
```

—

## Implicit function return `any`

When a function lacks a return type annotation and TypeScript infers `any` from its body, that `any` silently escapes:

```typescript
// ❌ TypeScript infers return type as any — propagates silently
function parseConfig(json: string) {
  return JSON.parse(json); // return type: any
}
const config = parseConfig(‘{}’);
config.port.toString(); // no error — crash if port doesn’t exist
```

```typescript
// ✅ Annotate the return type — forces you to handle the shape
function parseConfig(json: string): AppConfig {
  const raw = JSON.parse(json) as unknown;
  return AppConfigSchema.parse(raw); // or a type guard
}

// ✅ Or use a runtime validator
const parseConfig = (json: string): AppConfig => AppConfigSchema.parse(JSON.parse(json));
```

—

## Not handling Promise rejections

Unhandled promise rejections crash Node.js apps and produce silent failures in browsers:

```typescript
// ❌ Missing await — returns a Promise, doesn’t handle rejection
async function loadUsers() {
  fetchUsers(); // TypeScript doesn’t error — but rejection is unhandled
  return ‘done’;
}

// ❌ Not catching — unhandled if fetchUsers rejects
async function loadUsers() {
  const users = await fetchUsers();
  return users;
}

// ✅ Always handle rejections explicitly
async function loadUsers(): Promise<User[]> {
  try {
    return await fetchUsers();
  } catch (e) {
    logger.error(‘Failed to load users’, e);
    return [];
  }
}
```

Enable `@typescript-eslint/no-floating-promises` in your ESLint config — it catches unawaited async calls that are returned or discarded without handling.