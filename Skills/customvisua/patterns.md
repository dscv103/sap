# Advanced Type Patterns

## Table of Contents
- [Narrowing and Type Guards](#narrowing-and-type-guards)
- [Discriminated Unions in Depth](#discriminated-unions-in-depth)
- [Generics in Depth](#generics-in-depth)
- [Utility Type Recipes](#utility-type-recipes)
- [The `satisfies` Operator](#the-satisfies-operator)
- [Template Literal Types](#template-literal-types)
- [Mapped Types](#mapped-types)
- [Conditional Types](#conditional-types)
- [Branded / Nominal Types](#branded—nominal-types)
- [Runtime Validation with Zod](#runtime-validation-with-zod)

—

## Narrowing and Type Guards

TypeScript narrows types through control flow analysis. Use these mechanisms, in order of preference:

### 1. `typeof` — for primitives
```typescript
function process(value: string | number) {
  if (typeof value === ‘string’) {
    return value.toUpperCase(); // value: string
  }
  return value.toFixed(2);     // value: number
}
```

### 2. `instanceof` — for class instances
```typescript
function handle(error: Error | TypeError | RangeError) {
  if (error instanceof TypeError) {
    // error: TypeError — has all TypeError methods
  }
}
```

### 3. `in` — for property existence
```typescript
type Cat = { meow(): void };
type Dog = { bark(): void };
function makeNoise(animal: Cat | Dog) {
  if (‘meow’ in animal) {
    animal.meow(); // animal: Cat
  } else {
    animal.bark(); // animal: Dog
  }
}
```

### 4. Discriminant property — for object unions
```typescript
type Shape =
  | { kind: ‘circle’; radius: number }
  | { kind: ‘rect’; width: number; height: number };

function area(shape: Shape) {
  if (shape.kind === ‘circle’) {
    return Math.PI * shape.radius ** 2; // shape: { kind: ‘circle’; radius: number }
  }
  return shape.width * shape.height; // shape: { kind: ‘rect’; ... }
}
```

### 5. Custom type predicates — for reusable checks
```typescript
function isUser(value: unknown): value is User {
  return (
    typeof value === ‘object’ &&
    value !== null &&
    ‘id’ in value && typeof (value as any).id === ‘string’ &&
    ‘name’ in value && typeof (value as any).name === ‘string’
  );
}

// Use it anywhere:
const data: unknown = await fetchData();
if (isUser(data)) {
  console.log(data.name); // data: User
}
```

### 6. Assertion functions — for throwing on bad data
```typescript
function assertIsString(val: unknown): asserts val is string {
  if (typeof val !== ‘string’) {
    throw new TypeError(`Expected string, got ${typeof val}`);
  }
}

function processInput(input: unknown) {
  assertIsString(input);
  input.toUpperCase(); // after the assert, TypeScript knows input is string
}
```

### Exhaustiveness with `never`
```typescript
function assertNever(x: never): never {
  throw new Error(`Unhandled case: ${JSON.stringify(x)}`);
}

type Status = ‘active’ | ‘inactive’ | ‘pending’;
function getLabel(status: Status): string {
  switch (status) {
    case ‘active’:   return ‘Active’;
    case ‘inactive’: return ‘Inactive’;
    case ‘pending’:  return ‘Pending’;
    default:         return assertNever(status); // compile error if a case is missing
  }
}
```

—

## Discriminated Unions in Depth

The discriminant property must be a **literal type** (string literal, numeric literal, boolean literal, `null`, or `undefined`). All members of the union must have it.

### API response pattern
```typescript
type ApiResult<T> =
  | { status: ‘success’; data: T; statusCode: number }
  | { status: ‘error’; message: string; statusCode: number }
  | { status: ‘loading’ };

function renderUser(result: ApiResult<User>) {
  switch (result.status) {
    case ‘loading’: return <Spinner />;
    case ‘success’: return <Profile user={result.data} />;
    case ‘error’:   return <ErrorBanner message={result.message} />;
  }
}
```

### Action pattern (Redux-style)
```typescript
type Action =
  | { type: ‘ADD_ITEM’; payload: CartItem }
  | { type: ‘REMOVE_ITEM’; itemId: string }
  | { type: ‘CLEAR_CART’ };

function reducer(state: CartState, action: Action): CartState {
  switch (action.type) {
    case ‘ADD_ITEM’:    return { ...state, items: [...state.items, action.payload] };
    case ‘REMOVE_ITEM’: return { ...state, items: state.items.filter(i => i.id !== action.itemId) };
    case ‘CLEAR_CART’:  return { ...state, items: [] };
  }
}
```

### Extracting specific variants
```typescript
type SuccessResult = Extract<ApiResult<User>, { status: ‘success’ }>;
// { status: ‘success’; data: User; statusCode: number }

type NonLoadingResult = Exclude<ApiResult<User>, { status: ‘loading’ }>;
// ApiResult<User> without the loading branch
```

—

## Generics in Depth

### Constraints with `extends`
```typescript
// T must have an id property
function findById<T extends { id: string }>(collection: T[], id: string): T | undefined {
  return collection.find(item => item.id === id);
}

// K must be a key of T
function pluck<T, K extends keyof T>(items: T[], key: K): T[K][] {
  return items.map(item => item[key]);
}
const names = pluck(users, ‘name’); // string[]
```

### Inferred types with `infer`
```typescript
// Unwrap the element type of an array
type ElementOf<T> = T extends (infer E)[] ? E : never;
type UserFromArray = ElementOf<User[]>; // User

// Unwrap a Promise
type Awaited<T> = T extends Promise<infer R> ? Awaited<R> : T;

// Get the first argument type of a function
type FirstArg<F> = F extends (first: infer A, ...rest: any[]) => any ? A : never;
```

### Generic classes
```typescript
class Repository<T extends { id: string }> {
  private store = new Map<string, T>();

  save(entity: T): void { this.store.set(entity.id, entity); }
  findById(id: string): T | undefined { return this.store.get(id); }
  findAll(): T[] { return [...this.store.values()]; }
  delete(id: string): boolean { return this.store.delete(id); }
}

const users = new Repository<User>();  // TypeScript infers all types
```

### Default type parameters
```typescript
type PaginatedResponse<T, Meta = { total: number; page: number }> = {
  items: T[];
  meta: Meta;
};

type UserPage = PaginatedResponse<User>;              // uses default Meta
type CustomPage = PaginatedResponse<Post, { cursor: string }>; // custom Meta
```

—

## Utility Type Recipes

### Building domain types from a base entity
```typescript
interface User {
  id: string;
  name: string;
  email: string;
  passwordHash: string;
  createdAt: Date;
  updatedAt: Date;
}

type PublicUser    = Omit<User, ‘passwordHash’>;
type CreateUserDto = Omit<User, ‘id’ | ‘createdAt’ | ‘updatedAt’>;
type UpdateUserDto = Partial<Omit<User, ‘id’ | ‘createdAt’ | ‘updatedAt’>>;
type UserSummary   = Pick<User, ‘id’ | ‘name’ | ‘email’>;
```

### Record for lookup tables
```typescript
type Role = ‘admin’ | ‘editor’ | ‘viewer’;
const permissions: Record<Role, string[]> = {
  admin:  [‘read’, ‘write’, ‘delete’],
  editor: [‘read’, ‘write’],
  viewer: [‘read’],
};
// TypeScript errors if you miss a role or use an unknown role
```

### ReturnType / Parameters for wrapping functions
```typescript
declare function fetchUser(id: string): Promise<User>;

type FetchUserReturn = Awaited<ReturnType<typeof fetchUser>>; // User
type FetchUserArgs   = Parameters<typeof fetchUser>;          // [id: string]

// Useful for creating wrappers that preserve types
function withLogging<F extends (...args: any[]) => any>(fn: F): F {
  return ((...args: Parameters<F>) => {
    console.log(‘calling with’, args);
    return fn(...args);
  }) as F;
}
```

### Deep readonly
```typescript
type DeepReadonly<T> = {
  readonly [K in keyof T]: T[K] extends object ? DeepReadonly<T[K]> : T[K];
};

type ImmutableConfig = DeepReadonly<Config>;
```

—

## The `satisfies` Operator

`satisfies` validates that a value matches a type without widening it. The best of both worlds: type safety *and* preserved literal types for inference.

```typescript
type Palette = Record<string, string | [number, number, number]>;

// ✅ satisfies — validates the shape, preserves literal types
const theme = {
  red:   [255, 0, 0],    // inferred as [number, number, number], not (number|string)[]
  green: ‘#00ff00’,      // inferred as string
  blue:  [0, 0, 255],
} satisfies Palette;

theme.red.map(v => v * 2);   // ✅ TypeScript knows it’s a number tuple
theme.green.toUpperCase();   // ✅ TypeScript knows it’s a string

// vs. explicit annotation — loses literal types:
const theme2: Palette = { red: [255, 0, 0], ... };
theme2.red.map(...); // ❌ Error: ‘string | [number, number, number]’ has no .map
```

Use `satisfies` when you want compile-time validation but need to preserve the specific inferred types for downstream use.

```typescript
// Config object: validate shape, keep literal values
const config = {
  port: 3000,
  host: ‘localhost’,
  debug: true,
} satisfies Partial<ServerConfig>;
// port is 3000 (literal), not number
```

—

## Template Literal Types

Useful for typed event systems, URL patterns, CSS class naming, and any string-based convention.

```typescript
// Event system
type EventName = ‘click’ | ‘focus’ | ‘blur’ | ‘change’;
type EventHandler = `on${Capitalize<EventName>}`;
// ‘onClick’ | ‘onFocus’ | ‘onBlur’ | ‘onChange’

// API endpoint typing
type HttpMethod = ‘GET’ | ‘POST’ | ‘PUT’ | ‘DELETE’;
type Endpoint = `/api/${string}`;

function request(method: HttpMethod, url: Endpoint) { ... }
request(‘GET’, ‘/api/users’);   // ✅
request(‘GET’, ‘/users’);       // ❌ must start with /api/

// CSS variable typing
type ColorScale = 100 | 200 | 300 | 400 | 500 | 600 | 700 | 800 | 900;
type ColorName = ‘gray’ | ‘blue’ | ‘red’ | ‘green’;
type CssVar = `—color-${ColorName}-${ColorScale}`;
// ‘—color-gray-100’ | ‘—color-gray-200’ | ... | ‘—color-green-900’
```

—

## Mapped Types

Transform every property of a type systematically.

```typescript
// Make all properties nullable
type Nullable<T> = { [K in keyof T]: T[K] | null };

// Make specific keys required, rest optional
type RequiredKeys<T, K extends keyof T> =
  Required<Pick<T, K>> & Partial<Omit<T, K>>;

// Convert all function values to their return types
type ResolvedValues<T> = {
  [K in keyof T]: T[K] extends () => infer R ? R : T[K];
};

// Feature flags from a type
type FeatureFlags<T> = { [K in keyof T]: boolean };
type Flags = FeatureFlags<{ darkMode: unknown; notifications: unknown }>;
// { darkMode: boolean; notifications: boolean }
```

—

## Conditional Types

```typescript
// IsArray: true if T is an array, else false
type IsArray<T> = T extends any[] ? true : false;
type A = IsArray<string[]>; // true
type B = IsArray<string>;   // false

// Flatten: unwrap one level of array
type Flatten<T> = T extends (infer E)[] ? E : T;
type C = Flatten<string[]>; // string
type D = Flatten<string>;   // string (passthrough)

// Practical: deep partial
type DeepPartial<T> = T extends object
  ? { [K in keyof T]?: DeepPartial<T[K]> }
  : T;
```

—

## Branded / Nominal Types

TypeScript uses structural typing — two types with the same shape are interchangeable. Branded types add nominal identity to prevent mixing up structurally identical types.

```typescript
// Without branding: strings are all interchangeable
declare function getUser(userId: string): User;
declare function getOrder(orderId: string): Order;
const userId = ‘user-123’;
getOrder(userId); // ✅ TypeScript allows — but logically wrong!

// With branding: structurally identical but type-incompatible
type UserId  = string & { readonly _brand: ‘UserId’ };
type OrderId = string & { readonly _brand: ‘OrderId’ };

function makeUserId(id: string): UserId   { return id as UserId; }
function makeOrderId(id: string): OrderId { return id as OrderId; }

declare function getUser(userId: UserId): User;
declare function getOrder(orderId: OrderId): Order;

const userId  = makeUserId(‘user-123’);
const orderId = makeOrderId(‘order-456’);
getOrder(userId);  // ❌ compile error — UserId is not assignable to OrderId
getUser(orderId);  // ❌ compile error — correct!
```

Common uses: currency values, validated emails, sanitized strings, entity IDs.

—

## Runtime Validation with Zod

TypeScript types are erased at runtime. When data comes from outside your codebase (API responses, user input, environment variables, localStorage), use a runtime validator to bridge the gap.

```typescript
import { z } from ‘zod’;

// Define schema — Zod infers the TypeScript type from it
const UserSchema = z.object({
  id: z.string().uuid(),
  name: z.string().min(1).max(100),
  email: z.string().email(),
  role: z.enum([‘admin’, ‘editor’, ‘viewer’]),
  createdAt: z.coerce.date(),
});

// Infer the TS type — single source of truth
type User = z.infer<typeof UserSchema>;

// Parse at the trust boundary
async function fetchUser(id: string): Promise<User> {
  const response = await fetch(`/api/users/${id}`);
  const raw = await response.json();
  return UserSchema.parse(raw); // throws ZodError if shape is wrong
}

// Safe parse (returns result object instead of throwing)
const result = UserSchema.safeParse(unknownData);
if (result.success) {
  console.log(result.data.name); // User
} else {
  console.error(result.error.flatten());
}
```

**Rule of thumb**: Define your types *once* as Zod schemas at trust boundaries, then derive TypeScript types from them with `z.infer<>`. Never define the type separately and the schema separately — that creates two sources of truth that can drift.