// Adds the "generated, do not edit" header to the generated API types.
import { readFileSync, writeFileSync } from 'node:fs'

const file = 'src/lib/api/schema.d.ts'
const header = '// Generated from the FastAPI OpenAPI schema (apps/api/openapi.json). Do not hand-edit.\n// Run `npm run gen:api` to refresh it.\n'
const text = readFileSync(file, 'utf8')
if (!text.startsWith('// Generated from')) writeFileSync(file, header + text)
