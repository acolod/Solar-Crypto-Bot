import { useEffect, type ReactNode } from "react";
import { applyTheme, getThemeByName, type ThemeConfig } from "@/lib/theme-config";

type ThemeMode = "light" | "dark" | "system";

interface ThemeInitializerProps {
  children: ReactNode;
  theme?: string | ThemeConfig;
  mode?: ThemeMode;
}

/**
 * ThemeInitializer - Component that applies a theme on mount and whenever props change
 * 
 * @param theme - Theme name (string) or ThemeConfig object
 * @param mode - "light", "dark", or "system" (defaults to "system")
 * @param children - Children components
 */
export function ThemeInitializer({ 
  children, 
  theme = "default", 
  mode = "system"
}: ThemeInitializerProps) {
  useEffect(() => {
    // Initialize theme
    initializeTheme(theme, mode);
    
    // Set up system theme listener if needed
    if (mode === "system") {
      const mediaQuery = window.matchMedia("(prefers-color-scheme: dark)");
      
      const handleChange = () => {
        initializeTheme(theme, mode);
      };
      
      mediaQuery.addEventListener("change", handleChange);
      return () => mediaQuery.removeEventListener("change", handleChange);
    }
  }, [theme, mode]);
  
  return <>{children}</>;
}

// Helper function for theme initialization
function initializeTheme(theme: string | ThemeConfig, mode: ThemeMode): void {
  let themeConfig: ThemeConfig | undefined;
  
  // Get theme configuration
  if (typeof theme === "string") {
    themeConfig = getThemeByName(theme);
    if (!themeConfig) {
      console.warn(`Theme "${theme}" not found, using default theme.`);
      themeConfig = getThemeByName("default");
    }
  } else {
    themeConfig = theme;
  }
  
  if (!themeConfig) return;
  
  // Apply theme
  const isDarkMode = mode === "system" 
    ? window.matchMedia("(prefers-color-scheme: dark)").matches 
    : mode === "dark";
  
  applyTheme(themeConfig, isDarkMode);
}