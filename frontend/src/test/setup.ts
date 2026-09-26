import '@testing-library/jest-dom/vitest'
import { cleanup } from '@testing-library/react'
import { afterEach } from 'vitest'

// @testing-library/react's automatic afterEach cleanup only registers itself
// when it detects a global `afterEach` (i.e. Vitest's `globals: true`). Since
// this project keeps globals disabled, unmount explicitly so each test
// renders into a fresh DOM.
afterEach(() => {
  cleanup()
})
