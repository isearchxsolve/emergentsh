"""
Mobile Templates — Expo/React Native project scaffolding for mobile targets.
"""

from __future__ import annotations

import os
import shutil
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from ..workspace import WorkspaceManager, get_workspace, Project


# ════════════════════════════════════════════════════════════════════════════
# Template Definitions
# ════════════════════════════════════════════════════════════════════════════

@dataclass
class MobileTemplate:
    """Mobile app template definition."""
    key: str
    name: str
    description: str
    framework: str  # "expo", "react-native-cli", "flutter"
    language: str  # "typescript", "javascript"
    features: List[str]
    dependencies: Dict[str, str]  # package -> version
    dev_dependencies: Dict[str, str]
    scripts: Dict[str, str]
    files: Dict[str, str]  # relative_path -> template_content


# ════════════════════════════════════════════════════════════════════════════
# Built-in Mobile Templates
# ════════════════════════════════════════════════════════════════════════════

MOBILE_TEMPLATES: Dict[str, MobileTemplate] = {
    "expo-router-ts": MobileTemplate(
        key="expo-router-ts",
        name="Expo Router + TypeScript",
        description="File-based routing with Expo Router, TypeScript, and NativeWind",
        framework="expo",
        language="typescript",
        features=["expo-router", "nativewind", "typescript", "expo-dev-client"],
        dependencies={
            "expo": "~51.0.0",
            "expo-router": "~3.5.0",
            "expo-dev-client": "~4.0.0",
            "react": "18.2.0",
            "react-native": "0.74.0",
            "react-dom": "18.2.0",
            "nativewind": "^4.1.0",
            "@expo/vector-icons": "^14.0.0",
            "react-native-reanimated": "~3.10.0",
            "react-native-gesture-handler": "~2.16.0",
            "react-native-screens": "~3.31.0",
            "react-native-safe-area-context": "4.10.0",
            "expo-linking": "~6.3.0",
            "expo-constants": "~16.0.0",
            "expo-status-bar": "~1.12.0",
        },
        dev_dependencies={
            "typescript": "^5.4.0",
            "@types/react": "~18.2.0",
            "@types/react-native": "~0.73.0",
            "tailwindcss": "^3.4.0",
            "prettier": "^3.2.0",
            "prettier-plugin-tailwindcss": "^0.5.0",
            "@babel/core": "^7.24.0",
            "@babel/preset-typescript": "^7.24.0",
        },
        scripts={
            "start": "expo start",
            "android": "expo start --android",
            "ios": "expo start --ios",
            "web": "expo start --web",
            "build:android": "eas build --platform android",
            "build:ios": "eas build --platform ios",
            "lint": "eslint . --ext .ts,.tsx",
            "typecheck": "tsc --noEmit",
            "format": "prettier --write .",
        },
        files={
            "package.json": """{
  "name": "{{project_name_kebab}}",
  "version": "1.0.0",
  "main": "expo-router/entry",
  "scripts": {{scripts}},
  "dependencies": {{dependencies}},
  "devDependencies": {{dev_dependencies}},
  "private": true,
  "expo": {
    "name": "{{project_name}}",
    "slug": "{{project_name_kebab}}",
    "scheme": "{{project_name_kebab}}",
    "orientation": "portrait",
    "icon": "./assets/icon.png",
    "userInterfaceStyle": "automatic",
    "splash": {
      "image": "./assets/splash.png",
      "resizeMode": "contain",
      "backgroundColor": "#1a1b26"
    },
    "updates": {
      "fallbackToCacheTimeout": 0
    },
    "assetBundlePatterns": ["**/*"],
    "ios": {
      "supportsTablet": true,
      "bundleIdentifier": "com.{{organization}}.{{project_name_kebab}}"
    },
    "android": {
      "adaptiveIcon": {
        "foregroundImage": "./assets/adaptive-icon.png",
        "backgroundColor": "#1a1b26"
      },
      "package": "com.{{organization}}.{{project_name_kebab}}"
    },
    "web": {
      "favicon": "./assets/favicon.png"
    },
    "plugins": [
      "expo-router",
      "expo-dev-client",
      ["nativewind", { "input": "./global.css" }]
    ],
    "experiments": {
      "typedRoutes": true
    }
  }
}""",
            "tsconfig.json": """{
  "compilerOptions": {
    "target": "ES2020",
    "lib": ["ES2020", "DOM", "DOM.Iterable"],
    "module": "ESNext",
    "moduleResolution": "bundler",
    "jsx": "react-jsx",
    "strict": true,
    "noEmit": true,
    "esModuleInterop": true,
    "allowSyntheticDefaultImports": true,
    "forceConsistentCasingInFileNames": true,
    "resolveJsonModule": true,
    "isolatedModules": true,
    "noUnusedLocals": true,
    "noUnusedParameters": true,
    "noFallthroughCasesInSwitch": true,
    "baseUrl": ".",
    "paths": {
      "@/*": ["./*"],
      "@/components/*": ["./components/*"],
      "@/hooks/*": ["./hooks/*"],
      "@/lib/*": ["./lib/*"],
      "@/types/*": ["./types/*"]
    }
  },
  "include": ["**/*.ts", "**/*.tsx", ".expo/types/**/*.ts", "expo-env.d.ts"],
  "exclude": ["node_modules"]
}""",
            "tailwind.config.js": """/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./app/**/*.{js,jsx,ts,tsx}",
    "./components/**/*.{js,jsx,ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        primary: {
          DEFAULT: '#7aa2f7',
          foreground: '#1a1b26',
        },
        secondary: {
          DEFAULT: '#1f2335',
          foreground: '#c0caf5',
        },
        muted: {
          DEFAULT: '#1f2335',
          foreground: '#565f89',
        },
        accent: {
          DEFAULT: '#e0af68',
          foreground: '#1a1b26',
        },
        destructive: {
          DEFAULT: '#f7768e',
          foreground: '#1a1b26',
        },
        background: '#1a1b26',
        foreground: '#c0caf5',
        card: '#16161e',
        'card-foreground': '#c0caf5',
        border: '#1f2335',
        input: '#1f2335',
        ring: '#7aa2f7',
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'monospace'],
      },
      borderRadius: {
        lg: '0.5rem',
        md: '0.375rem',
        sm: '0.25rem',
      },
    },
  },
  plugins: [],
}""",
            "global.css": """@tailwind base;
@tailwind components;
@tailwind utilities;

@layer base {
  :root {
    --background: 26 27 38;
    --foreground: 192 202 245;
    --card: 22 22 30;
    --card-foreground: 192 202 245;
    --primary: 122 162 247;
    --primary-foreground: 26 27 38;
    --secondary: 31 35 53;
    --secondary-foreground: 192 202 245;
    --muted: 31 35 53;
    --muted-foreground: 86 95 137;
    --accent: 224 175 104;
    --accent-foreground: 26 27 38;
    --destructive: 247 118 142;
    --destructive-foreground: 26 27 38;
    --border: 31 35 53;
    --input: 31 35 53;
    --ring: 122 162 247;
    --radius: 0.5rem;
  }
}

* {
  border-color: hsl(var(--border));
}

body {
  background-color: hsl(var(--background));
  color: hsl(var(--foreground));
  font-feature-settings: "rlig" 1, "calt" 1;
}

@layer utilities {
  .text-balance {
    text-wrap: balance;
  }
}""",
            "app/_layout.tsx": """import { Stack } from 'expo-router';
import { SafeAreaProvider } from 'react-native-safe-area-context';
import { GestureHandlerRootView } from 'react-native-gesture-handler';
import { Providers } from '@/providers';
import { Toaster } from 'react-hot-toast';

export default function RootLayout() {
  return (
    <SafeAreaProvider>
      <GestureHandlerRootView style={{ flex: 1 }}>
        <Providers>
          <Stack
            screenOptions={{
              headerShown: false,
              contentStyle: { backgroundColor: '#1a1b26' },
            }}
          >
            <Stack.Screen name="(tabs)" options={{ headerShown: false }} />
            <Stack.Screen name="+not-found" options={{ headerShown: false }} />
          </Stack>
        </Providers>
        <Toaster
          position="bottom-right"
          toastOptions={{
            style: { backgroundColor: '#1f2335', color: '#c0caf5' },
            success: { iconTheme: { primary: '#9ece6a', secondary: '#1a1b26' } },
            error: { iconTheme: { primary: '#f7768e', secondary: '#1a1b26' } },
          }}
        />
      </GestureHandlerRootView>
    </SafeAreaProvider>
  );
}""",
            "app/(tabs)/_layout.tsx": """import { Tabs } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { useColorScheme } from 'react-native';
import { useColorScheme } from '@/hooks/useColorScheme';

export default function TabLayout() {
  const colorScheme = useColorScheme();

  return (
    <Tabs
      screenOptions={{
        tabBarActiveTintColor: '#7aa2f7',
        tabBarInactiveTintColor: '#565f89',
        tabBarStyle: {
          backgroundColor: '#16161e',
          borderTopWidth: 0,
          height: 60,
          paddingBottom: 8,
        },
        tabBarIconStyle: { marginBottom: 2 },
      }}
    >
      <Tabs.Screen
        name="index"
        options={{
          title: 'Home',
          tabBarIcon: ({ color, size }) => (
            <Ionicons name="home-outline" size={size} color={color} />
          ),
        }}
      />
      <Tabs.Screen
        name="explore"
        options={{
          title: 'Explore',
          tabBarIcon: ({ color, size }) => (
            <Ionicons name="compass-outline" size={size} color={color} />
          ),
        }}
      />
      <Tabs.Screen
        name="settings"
        options={{
          title: 'Settings',
          tabBarIcon: ({ color, size }) => (
            <Ionicons name="settings-outline" size={size} color={color} />
          ),
        }}
      />
    </Tabs>
  );
}""",
            "app/index.tsx": """import { View, Text, StyleSheet, SafeAreaView, ScrollView } from 'react-native';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Sparkles, Zap, Smartphone, Code, Globe } from 'lucide-react-native';

export default function HomeScreen() {
  return (
    <SafeAreaView style={styles.container}>
      <ScrollView contentContainerStyle={styles.content}>
        <View style={styles.header}>
          <Text style={styles.title}>Welcome to EmergentSH Mobile</Text>
          <Text style={styles.subtitle}>
            Build mobile apps with AI-powered development
          </Text>
        </View>

        <View style={styles.grid}>
          <Card style={styles.card}>
            <CardHeader>
              <CardTitle>Expo Router</CardTitle>
              <CardDescription>File-based routing with native navigation</CardDescription>
            </CardHeader>
            <CardContent>
              <Text style={styles.featureText}>File-based routing with native navigation</Text>
            </CardContent>
          </Card>

          <Card style={styles.card}>
            <CardHeader>
              <CardTitle>NativeWind</CardTitle>
              <CardDescription>Tailwind CSS for React Native</CardDescription>
            </CardHeader>
            <CardContent>
              <Text style={styles.featureText}>Utility-first styling with Tailwind</Text>
            </CardContent>
          </Card>

          <Card style={styles.card}>
            <CardHeader>
              <CardTitle>TypeScript</CardTitle>
              <CardDescription>Full type safety across your app</CardDescription>
            </CardHeader>
            <CardContent>
              <Text style={styles.featureText}>End-to-end type safety</Text>
            </CardContent>
          </Card>

          <Card style={styles.card}>
            <CardHeader>
              <CardTitle>Expo Dev Client</CardTitle>
              <CardDescription>Custom native modules & debugging</CardDescription>
            </CardHeader>
            <CardContent>
              <Text style={styles.featureText}>Custom native modules support</Text>
            </CardContent>
          </Card>
        </View>

        <View style={styles.cta}>
          <Button variant="default" onPress={() => console.log('Get started')}>
            Get Started
          </Button>
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#1a1b26' },
  content: { padding: 20, paddingBottom: 40 },
  header: { marginBottom: 24 },
  title: { fontSize: 28, fontWeight: '700', color: '#c0caf5', marginBottom: 8 },
  subtitle: { fontSize: 16, color: '#565f89' },
  grid: { flexDirection: 'row', flexWrap: 'wrap', gap: 16, marginBottom: 24 },
  card: { width: '48%', minWidth: 160 },
  featureText: { fontSize: 13, color: '#a9b1d6', marginTop: 8 },
  cta: { paddingTop: 16, alignItems: 'center' },
};""",
            "components/ui/button.tsx": """import { Pressable, Text, StyleSheet } from 'react-native';
import { cn } from '@/lib/utils';

interface ButtonProps {
  children: React.ReactNode;
  onPress?: () => void;
  variant?: 'default' | 'outline' | 'ghost' | 'destructive';
  size?: 'sm' | 'md' | 'lg';
  disabled?: boolean;
  className?: string;
  style?: any;
}

export function Button({
  children,
  onPress,
  variant = 'default',
  size = 'md',
  disabled = false,
  className,
  style,
  ...props
}) {
  const baseStyles = [
    styles.base,
    styles[variant],
    styles[size],
    disabled && styles.disabled,
    style,
  ];

  return (
    <Pressable
      onPress={onPress}
      disabled={disabled}
      style={baseStyles}
      android_ripple={{ color: '#7aa2f733' }}
      {...props}
    >
      <Text style={styles.text}>{children}</Text>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  base: {
    borderRadius: 8,
    justifyContent: 'center',
    alignItems: 'center',
    flexDirection: 'row',
    gap: 8,
  },
  default: {
    backgroundColor: '#7aa2f7',
    borderWidth: 0,
  },
  outline: {
    backgroundColor: 'transparent',
    borderWidth: 1,
    borderColor: '#7aa2f7',
  },
  ghost: {
    backgroundColor: 'transparent',
    borderWidth: 0,
  },
  destructive: {
    backgroundColor: '#f7768e',
    borderWidth: 0,
  },
  sm: { paddingHorizontal: 12, paddingVertical: 8 },
  md: { paddingHorizontal: 16, paddingVertical: 10 },
  lg: { paddingHorizontal: 24, paddingVertical: 12 },
  disabled: { opacity: 0.5 },
  text: {
    fontSize: 14,
    fontWeight: '600',
  },
});
""",
            "components/ui/card.tsx": """import { View, Text, StyleSheet } from 'react-native';
import { cn } from '@/lib/utils';

interface CardProps {
  children: React.ReactNode;
  className?: string;
  style?: any;
}

export function Card({ children, className, style }: CardProps) {
  return (
    <View style={[styles.card, style]} className={className}>
      {children}
    </View>
  );
}

interface CardHeaderProps {
  children: React.ReactNode;
  className?: string;
  style?: any;
}

export function CardHeader({ children, className, style }: CardHeaderProps) {
  return (
    <View style={[styles.cardHeader, style]} className={className}>
      {children}
    </View>
  );
}

interface CardTitleProps {
  children: React.ReactNode;
  className?: string;
  style?: any;
}

export function CardTitle({ children, className, style }: CardTitleProps) {
  return (
    <Text style={[styles.cardTitle, style]} className={className}>
      {children}
    </Text>
  );
}

interface CardDescriptionProps {
  children: React.ReactNode;
  className?: string;
  style?: any;
}

export function CardDescription({ children, className, style }: CardDescriptionProps) {
  return (
    <Text style={[styles.cardDescription, style]} className={className}>
      {children}
    </Text>
  );
}

interface CardContentProps {
  children: React.ReactNode;
  className?: string;
  style?: any;
}

export function CardContent({ children, className, style }: CardContentProps) {
  return (
    <View style={[styles.cardContent, style]} className={className}>
      {children}
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: '#16161e',
    borderRadius: 12,
    borderWidth: 1,
    borderColor: '#1f2335',
    overflow: 'hidden',
  },
  cardHeader: {
    padding: 16,
    paddingBottom: 8,
  },
  cardTitle: {
    fontSize: 16,
    fontWeight: '600',
    color: '#c0caf5',
    marginBottom: 4,
  },
  cardDescription: {
    fontSize: 13,
    color: '#565f89',
  },
  cardContent: {
    padding: 16,
    paddingTop: 0,
  },
});
""",
            "lib/utils.ts": """import { clsx, type ClassValue } from 'clsx';

export function cn(...inputs: ClassValue[]) {
  return clsx(inputs);
}

export function formatDate(date: Date | string): string {
  return new Date(date).toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  });
}

export function formatRelativeTime(date: Date | string): string {
  const now = new Date();
  const then = new Date(date);
  const diff = now.getTime() - then.getTime();

  const seconds = Math.floor(diff / 1000);
  const minutes = Math.floor(seconds / 60);
  const hours = Math.floor(minutes / 60);
  const days = Math.floor(hours / 24);

  if (days > 0) return `${days}d ago`;
  if (hours > 0) return `${hours}h ago`;
  if (minutes > 0) return `${minutes}m ago`;
  return 'just now';
}

export function truncate(str: string, length: number): string {
  if (str.length <= length) return str;
  return str.slice(0, length) + '...';
}

export function generateId(prefix = ''): string {
  return `${prefix}${Math.random().toString(36).substring(2, 15)}`;
}
""",
            "hooks/useColorScheme.ts": """import { useColorScheme } from 'react-native';

export function useColorScheme() {
  return useColorScheme();
}""",
            "providers/index.ts": """import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ReactQueryDevtools } from '@tanstack/react-query-devtools';
import { SessionProvider } from 'next-auth/react';
import { ThemeProvider } from 'next-themes';
import { Toaster } from 'react-hot-toast';
import { ReactNode } from 'react';

export function Providers({ children }: { children: React.ReactNode }) {
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            staleTime: 60 * 1000,
            refetchOnWindowFocus: false,
          },
        },
      })
  );

  return (
    <QueryClientProvider client={queryClient}>
      <SessionProvider>
        <ThemeProvider attribute="class" defaultTheme="system" enableSystem>
          {children}
          <Toaster
            position="bottom-right"
            toastOptions={{
              style: { backgroundColor: '#1f2335', color: '#c0caf5' },
              success: { iconTheme: { primary: '#9ece6a', secondary: '#1a1b26' } },
              error: { iconTheme: { primary: '#f7768e', secondary: '#1a1b26' } },
            }}
          />
          <ReactQueryDevtools initialIsOpen={false} />
        </ThemeProvider>
      </SessionProvider>
    </QueryClientProvider>
  );
}""",
            "app/(tabs)/index.tsx": """import { View, Text, StyleSheet, SafeAreaView, ScrollView } from 'react-native';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Sparkles, Zap, Smartphone, Code, Globe } from 'lucide-react-native';

export default function HomeScreen() {
  return (
    <SafeAreaView style={styles.container}>
      <ScrollView contentContainerStyle={styles.content}>
        <View style={styles.header}>
          <Text style={styles.title}>Welcome to EmergentSH Mobile</Text>
          <Text style={styles.subtitle}>
            Build mobile apps with AI-powered development
          </Text>
        </View>

        <View style={styles.grid}>
          <Card style={styles.card}>
            <CardHeader>
              <CardTitle>Expo Router</CardTitle>
              <CardDescription>File-based routing with native navigation</CardDescription>
            </CardHeader>
            <CardContent>
              <Text style={styles.featureText}>File-based routing with native navigation</Text>
            </CardContent>
          </Card>

          <Card style={styles.card}>
            <CardHeader>
              <CardTitle>NativeWind</CardTitle>
              <CardDescription>Tailwind CSS for React Native</CardDescription>
            </CardHeader>
            <CardContent>
              <Text style={styles.featureText}>Utility-first styling with Tailwind</Text>
            </CardContent>
          </Card>

          <Card style={styles.card}>
            <CardHeader>
              <CardTitle>TypeScript</CardTitle>
              <CardDescription>Full type safety across your app</CardDescription>
            </CardHeader>
            <CardContent>
              <Text style={styles.featureText}>End-to-end type safety</Text>
            </CardContent>
          </Card>

          <Card style={styles.card}>
            <CardHeader>
              <CardTitle>Expo Dev Client</CardTitle>
              <CardDescription>Custom native modules & debugging</CardDescription>
            </CardHeader>
            <CardContent>
              <Text style={styles.featureText}>Custom native modules support</Text>
            </CardContent>
          </Card>
        </View>

        <View style={styles.cta}>
          <Button variant="default" onPress={() => console.log('Get started')}>
            Get Started
          </Button>
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#1a1b26' },
  content: { padding: 20, paddingBottom: 40 },
  header: { marginBottom: 24 },
  title: { fontSize: 28, fontWeight: '700', color: '#c0caf5', marginBottom: 8 },
  subtitle: { fontSize: 16, color: '#565f89' },
  grid: { flexDirection: 'row', flexWrap: 'wrap', gap: 16, marginBottom: 24 },
  card: { width: '48%', minWidth: 160 },
  featureText: { fontSize: 13, color: '#a9b1d6', marginTop: 8 },
  cta: { paddingTop: 16, alignItems: 'center' },
});
""",
        },
    ),

    "expo-bare": MobileTemplate(
        key="expo-bare",
        name="Expo Bare Workflow",
        description="Expo with full native access, custom native code access",
        framework="expo",
        language="typescript",
        features=["expo", "bare-workflow", "native-modules"],
        dependencies={
            "expo": "~51.0.0",
            "expo-dev-client": "~4.0.0",
            "react": "18.2.0",
            "react-native": "0.74.0",
        },
        dev_dependencies={},
        scripts={
            "start": "expo start",
            "android": "expo run:android",
            "ios": "expo run:ios",
        },
        files={
            "package.json": "...",
            "app.json": "...",
        },
    ),

    "rn-cli": MobileTemplate(
        key="rn-cli",
        name="React Native CLI",
        description="Vanilla React Native with full native control",
        framework="react-native-cli",
        language="typescript",
        features=["react-native-cli", "typescript", "hermes"],
        dependencies={
            "react": "18.2.0",
            "react-native": "0.74.0",
        },
        dev_dependencies={
            "@types/react": "^18.2.0",
            "@types/react-native": "^0.73.0",
            "typescript": "^5.4.0",
        },
        scripts={},
        files={},
    ),
}


# ════════════════════════════════════════════════════════════════════════════
# Mobile Template Engine
# ════════════════════════════════════════════════════════════════════════════

class MobileTemplateEngine:
    """
    Generates mobile projects from templates.
    """

    def __init__(self, template_root: Optional[str] = None):
        self._template_root = Path(template_root) if template_root else Path(__file__).parent / "templates"
        self._templates = MOBILE_TEMPLATES

    def get_template(self, key: str) -> Optional[MobileTemplate]:
        return self._templates.get(key)

    def list_templates(self) -> List[MobileTemplate]:
        return list(self._templates.values())

    def generate(
        self,
        template_key: str,
        output_dir: str,
        context: Dict[str, Any],
    ) -> Dict[str, str]:
        """
        Generate a project from a template.
        
        Returns:
            Dict of generated file paths -> content
        """
        template = self.get_template(template_key)
        if not template:
            raise ValueError(f"Unknown template: {template_key}")

        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        # Build context with defaults
        full_context = self._build_context(context)

        generated = {}

        # Generate package.json first (needed for other files)
        if "package.json" in template.files:
            pkg_content = self._render_template(template.files["package.json"], full_context)
            pkg_path = output_path / "package.json"
            pkg_path.write_text(pkg_content)
            generated["package.json"] = pkg_content

        # Generate all other files
        for rel_path, template_content in template.files.items():
            if rel_path == "package.json":
                continue
            
            try:
                content = self._render_template(template_content, full_context)
                output_path = output_path / rel_path
                output_path.parent.mkdir(parents=True, exist_ok=True)
                output_path.write_text(content)
                generated[rel_path] = content
            except Exception as e:
                print(f"Warning: Failed to generate {rel_path}: {e}")

        return generated

    def _build_context(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Build template context with defaults."""
        project_name = context.get("project_name", "MyApp")
        project_name_kebab = project_name.lower().replace(" ", "-").replace("_", "-")
        organization = context.get("organization", "myorg")

        return {
            **context,
            "project_name": project_name,
            "project_name_kebab": project_name_kebab,
            "organization": organization,
            "scripts": json.dumps(context.get("scripts", {}), indent=2),
            "dependencies": json.dumps(context.get("dependencies", {}), indent=2),
            "dev_dependencies": json.dumps(context.get("dev_dependencies", {}), indent=2),
        }

    def _render_template(self, template_str: str, context: Dict[str, Any]) -> str:
        """Render template string with context."""
        # Simple template rendering (in production, use Jinja2)
        result = template_str
        for key, value in context.items():
            if isinstance(value, (dict, list)):
                value = json.dumps(value, indent=2)
            result = result.replace(f"{{{{{key}}}}}", str(value))
            result = result.replace(f"{{{{scripts}}}}", json.dumps(context.get("scripts", {}), indent=2))
            result = result.replace(f"{{{{dependencies}}}}", json.dumps(context.get("dependencies", {}), indent=2))
            result = result.replace(f"{{{{dev_dependencies}}}}", json.dumps(context.get("dev_dependencies", {}), indent=2))
        return result


# ════════════════════════════════════════════════════════════════════════════
# Expo Dev Client Integration
# ════════════════════════════════════════════════════════════════════════════

class ExpoDevClientManager:
    """
    Manages Expo dev client for device preview.
    
    Features:
    - QR code generation for device connection
    - Expo dev client build management
    - Live reload / HMR on device
    """

    def __init__(self, project_dir: str):
        self._project_dir = Path(project_dir)

    def generate_qr_code(self, port: int = 8081, host: str = "localhost") -> str:
        """Generate QR code data for Expo dev client connection."""
        import qrcode
        
        url = f"exp://{host}:{port}"
        qr = qrcode.QRCode(version=1, box_size=10, border=5)
        qr.add_data(url)
        qr.make(fit=True)
        
        img = qr.make_image(fill_color="black", back_color="white")
        
        # Save to temp file
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            img.save(f)
            return f.name

    def start_dev_server(self, port: int = 8081, tunnel: bool = False) -> subprocess.Popen:
        """Start Expo dev server."""
        cmd = ["npx", "expo", "start", "--port", str(port)]
        if tunnel:
            cmd.append("--tunnel")
        
        return subprocess.Popen(
            cmd,
            cwd=self._project_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )

    def build_dev_client(
        self,
        platform: str = "android",
        profile: str = "development",
    ) -> subprocess.CompletedProcess:
        """Build Expo dev client for device."""
        cmd = ["eas", "build", "--profile", profile, "--platform", platform, "--local"]
        
        return subprocess.run(
            cmd,
            cwd=self._project_dir,
            capture_output=True,
            text=True,
            timeout=1800,  # 30 minutes
        )

    def install_dev_client(self, device_id: Optional[str] = None) -> bool:
        """Install dev client on connected device."""
        cmd = ["adb"]
        if device_id:
            cmd.extend(["-s", device_id])
        cmd.extend(["install", "-r"])
        
        # Find the built APK
        apk_path = self._find_apk()
        if not apk_path:
            return False
        
        cmd.append(str(apk_path))
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        return result.returncode == 0

    def _find_apk(self) -> Optional[Path]:
        """Find the built APK."""
        build_dir = self._project_dir / "android" / "app" / "build" / "outputs" / "apk"
        if build_dir.exists():
            apks = list(build_dir.rglob("*.apk"))
            if apks:
                return max(apks, key=lambda p: p.stat().st_mtime)
        return None


# ════════════════════════════════════════════════════════════════════════════
# Device Preview Widget
# ════════════════════════════════════════════════════════════════════════════

try:
    from PySide6.QtCore import Qt, QUrl, Signal, Slot, QTimer
    from PySide6.QtWebEngineWidgets import QWebEngineView
    from PySide6.QtWebEngineCore import QWebEngineProfile, QWebEnginePage
    from PySide6.QtWidgets import (
        QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
        QLineEdit, QSpinBox, QComboBox, QGroupBox, QFormLayout
    )
    from PySide6.QtGui import QPixmap, QIcon
    from PySide6.QtCore import QUrl, QTimer
    
    class MobilePreviewWidget(QWidget):
        """
        Mobile device preview widget with Expo dev client integration.
        
        Features:
        - Embedded Expo web preview
        - QR code for device connection
        - Device frame simulation
        - Expo dev client integration
        """
        
        device_connected = Signal(str)  # device_id
        preview_refreshed = Signal()
        
        def __init__(self, project_dir: str, parent=None):
            super().__init__(parent)
            self._project_dir = Path(project_dir)
            self._expo_manager = ExpoDevClientManager(project_dir)
            self._dev_server_process = None
            self._port = 8081
            
            self._build_ui()
        
        def _build_ui(self):
            layout = QVBoxLayout(self)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(0)
            
            # Toolbar
            toolbar = self._create_toolbar()
            layout.addWidget(toolbar)
            
            # Preview area with device frame
            preview_frame = self._create_preview_frame()
            layout.addWidget(preview_frame, stretch=1)
            
            # Device controls
            controls = self._create_device_controls()
            layout.addWidget(controls)
        
        def _create_toolbar(self):
            toolbar = QWidget()
            layout = QHBoxLayout(toolbar)
            layout.setContentsMargins(8, 8, 8, 8)
            
            # Device selector
            self._device_combo = QComboBox()
            self._device_combo.addItems([
                "iPhone 15 Pro (393x852)",
                "iPhone 15 (390x844)",
                "iPhone SE (375x667)",
                "iPad Pro 12.9\" (1024x1366)",
                "iPad Mini (744x1133)",
                "Pixel 7 Pro (412x892)",
                "Pixel 7 (412x915)",
                "Galaxy S23 (360x780)",
                "Galaxy S23 Ultra (360x780)",
                "Custom...",
            ])
            self._device_combo.currentTextChanged.connect(self._on_device_changed)
            layout.addWidget(QLabel("Device:"))
            layout.addWidget(self._device_combo)
            
            layout.addStretch()
            
            # QR Code button
            self._qr_btn = QPushButton("📱 QR Code")
            self._qr_btn.clicked.connect(self._show_qr_code)
            layout.addWidget(self._qr_btn)
            
            # Refresh button
            self._refresh_btn = QPushButton("🔄 Refresh")
            self._refresh_btn.clicked.connect(self._refresh_preview)
            layout.addWidget(self._refresh_btn)
            
            return toolbar
        
        def _create_preview_frame(self):
            """Create the preview area with device frame."""
            frame = QWidget()
            layout = QVBoxLayout(frame)
            layout.setContentsMargins(0, 0, 0, 0)
            
            # Device frame container
            self._frame_container = QWidget()
            self._frame_container.setStyleSheet("""
                background-color: #1a1b26;
                border-radius: 24px;
                border: 4px solid #1f2335;
            """)
            self._frame_container.setFixedSize(393, 852)  # iPhone 15 Pro default
            
            frame_layout = QVBoxLayout(self._frame_container)
            frame_layout.setContentsMargins(0, 0, 0, 0)
            
            # Web view for Expo preview
            self._web_view = QWebEngineView()
            self._web_view.setUrl(QUrl(f"http://localhost:8081"))
            frame_layout.addWidget(self._web_view)
            
            layout.addWidget(self._frame_container, alignment=Qt.AlignCenter)
            
            return frame
        
        def _create_device_controls(self):
            controls = QWidget()
            layout = QHBoxLayout(controls)
            layout.setContentsMargins(16, 8, 16, 8)
            
            # Orientation toggle
            self._orientation_btn = QPushButton("🔄 Rotate")
            self._orientation_btn.setCheckable(True)
            self._orientation_btn.clicked.connect(self._toggle_orientation)
            layout.addWidget(self._orientation_btn)
            
            # Scale slider
            self._scale_spin = QSpinBox()
            self._scale_spin.setRange(25, 200)
            self._scale_spin.setValue(100)
            self._scale_spin.setSuffix("%")
            self._scale_spin.valueChanged.connect(self._on_scale_changed)
            layout.addWidget(QLabel("Scale:"))
            layout.addWidget(self._scale_spin)
            
            layout.addStretch()
            
            # Open in browser
            self._browser_btn = QPushButton("🌐 Open in Browser")
            self._browser_btn.clicked.connect(self._open_in_browser)
            layout.addWidget(self._browser_btn)
            
            return controls
        
        def _on_device_changed(self, text: str):
            """Handle device selection change."""
            sizes = {
                "iPhone 15 Pro (393x852)": (393, 852),
                "iPhone 15 (390x844)": (390, 844),
                "iPhone SE (375x667)": (375, 667),
                "iPad Pro 12.9\" (1024x1366)": (1024, 1366),
                "iPad Mini (744x1133)": (744, 1133),
                "Pixel 7 Pro (412x892)": (412, 892),
                "Pixel 7 (412x915)": (412, 915),
                "Galaxy S23 (360x780)": (360, 780),
                "Galaxy S23 Ultra (360x780)": (360, 780),
            }
            
            if text in sizes:
                w, h = sizes[text]
                self._frame_container.setFixedSize(w, h)
            elif text == "Custom...":
                # Show custom size dialog
                pass
        
        def _toggle_orientation(self, checked: bool):
            """Toggle device orientation."""
            if hasattr(self, '_frame_container'):
                size = self._frame_container.size()
                if checked:
                    self._frame_container.setFixedSize(size.height(), size.width())
                else:
                    self._frame_container.setFixedSize(size.width(), size.height())
        
        def _on_scale_changed(self, value: int):
            """Handle scale change."""
            self._frame_container.setTransformOriginPoint(
                self._frame_container.rect().center()
            )
            self._frame_container.setScale(value / 100.0)
        
        def _show_qr_code(self):
            """Show QR code for device connection."""
            from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel
            from PySide6.QtGui import QPixmap
            
            try:
                qr_path = self._expo_manager.generate_qr_code(self._port)
                dialog = QDialog(self)
                dialog.setWindowTitle("Scan with Expo Go")
                dialog.setModal(True)
                layout = QVBoxLayout(dialog)
                
                qr_label = QLabel()
                pixmap = QPixmap(qr_path)
                qr_label.setPixmap(pixmap.scaled(300, 300, Qt.KeepAspectRatio, Qt.SmoothTransformation))
                layout.addWidget(qr_label)
                
                info = QLabel("Scan with Expo Go or Expo Dev Client")
                info.setAlignment(Qt.AlignCenter)
                layout.addWidget(info)
                
                dialog.exec()
            except Exception as e:
                print(f"Failed to generate QR: {e}")
        
        def _refresh_preview(self):
            """Refresh the preview."""
            self._web_view.reload()
            self.preview_refreshed.emit()
        
        def _open_in_browser(self):
            """Open preview in external browser."""
            import webbrowser
            webbrowser.open(f"http://localhost:{self._port}")
        
        def start_preview(self, port: int = 8081):
            """Start the preview server."""
            self._port = port
            self._dev_server_process = self._expo_manager.start_dev_server(port)
            # Wait a moment for server to start, then load
            QTimer.singleShot(3000, lambda: self._web_view.setUrl(QUrl(f"http://localhost:{port}")))
        
        def stop_preview(self):
            """Stop the preview server."""
            if self._dev_server_process:
                self._dev_server_process.terminate()
                self._dev_server_process = None

except ImportError:
    # PySide6 not available
    class MobilePreviewWidget:
        pass


# ════════════════════════════════════════════════════════════════════════════
# Exports
# ════════════════════════════════════════════════════════════════════════════

__all__ = [
    "MobileTemplate",
    "MobileTemplateEngine",
    "ExpoDevClientManager",
    "MobilePreviewWidget",
    "MOBILE_TEMPLATES",
]