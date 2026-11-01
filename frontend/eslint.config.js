import js from '@eslint/js';
import globals from 'globals';
import tseslint from 'typescript-eslint';
import reactHooks from 'eslint-plugin-react-hooks';
import reactRefresh from 'eslint-plugin-react-refresh';
import vitest from '@vitest/eslint-plugin';
import testingLibrary from 'eslint-plugin-testing-library';
import jestDom from 'eslint-plugin-jest-dom';
import prettierConfig from 'eslint-config-prettier';

export default tseslint.config(
  {
    // `src/api/schema.d.ts` é gerado por `npm run generate:api-types` a partir
    // de `backend/openapi.json` e está no .gitignore: nunca deve ser lintado
    // nem formatado, sob pena de a próxima regeneração desfazer tudo.
    ignores: ['dist/**', 'node_modules/**', 'src/api/schema.d.ts'],
  },

  // Regras base para todo o código de aplicação.
  {
    files: ['**/*.{ts,tsx,js}'],
    extends: [js.configs.recommended, ...tseslint.configs.recommended],
    languageOptions: {
      ecmaVersion: 2022,
      sourceType: 'module',
      globals: globals.browser,
    },
    plugins: {
      'react-hooks': reactHooks,
      'react-refresh': reactRefresh,
    },
    rules: {
      ...reactHooks.configs.recommended.rules,
      // Correções de dependências/efeitos neste repositório são mudanças de
      // comportamento, não limpeza mecânica: as telas de Lançamento usam
      // refs e efeitos separados de propósito para não refazer o fetch (e
      // resetar o que o professor está digitando) a cada tecla. Ficam como
      // aviso, para avaliação pedagógica futura, nunca como gate de CI.
      'react-hooks/exhaustive-deps': 'warn',
      'react-hooks/refs': 'warn',
      'react-hooks/set-state-in-effect': 'warn',
      'react-refresh/only-export-components': [
        'warn',
        { allowConstantExport: true },
      ],
      '@typescript-eslint/no-unused-vars': [
        'error',
        { argsIgnorePattern: '^_', varsIgnorePattern: '^_' },
      ],
    },
  },

  // Arquivos de configuração executados em Node.
  {
    files: ['*.config.{ts,js}', 'vite.config.ts', 'eslint.config.js'],
    languageOptions: {
      globals: globals.node,
    },
  },

  // Testes: Vitest + Testing Library + jest-dom.
  {
    files: ['src/**/*.{test,spec}.{ts,tsx}', 'src/test/**/*.{ts,tsx}'],
    extends: [
      vitest.configs.recommended,
      testingLibrary.configs['flat/react'],
      jestDom.configs['flat/recommended'],
    ],
    languageOptions: {
      globals: vitest.environments.env.globals,
    },
    rules: {
      // Preferências de estilo de teste. Acusam padrões existentes que
      // funcionam (consulta via container, cleanup explícito no setup,
      // asserções dentro de helpers compartilhados). Reescrevê-los é
      // mudança de teste, fora do escopo deste PR mecânico: ficam como
      // aviso, para limpeza futura em um PR dedicado.
      'testing-library/no-node-access': 'warn',
      'testing-library/no-container': 'warn',
      'testing-library/no-manual-cleanup': 'warn',
      'vitest/expect-expect': 'warn',
    },
  },

  // Deve ser o último: desliga as regras de estilo do ESLint que
  // conflitariam com o Prettier (ESLint = regras, Prettier = formatação).
  prettierConfig,
);
