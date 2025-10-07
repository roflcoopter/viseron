import { useCallback, useContext, useEffect, useRef, useState } from "react";

import { ViseronContext } from "context/ViseronContext";
import { renderTemplate } from "lib/commands";

/**
 * Debounced template renderer hook.
 * Automatically renders the provided template after a debounce delay when it changes.
 * Exposes methods for manual render and clearing results.
 */
export function useDebouncedTemplateRender(template: string, delay = 500) {
  const { connection } = useContext(ViseronContext);

  const [result, setResult] = useState<string>("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const debounceTimeout = useRef<NodeJS.Timeout | null>(null);

  const renderNow = useCallback(async () => {
    if (!connection) {
      return;
    }
    setLoading(true);
    setResult("");
    try {
      const response = await renderTemplate(connection, template);
      setResult(response);
      setError(null);
    } catch (e: any) {
      setError(e?.message || "Failed to render template");
      setResult("");
    } finally {
      setLoading(false);
    }
  }, [connection, template]);

  useEffect(() => {
    if (!template) {
      setResult("");
      setError(null);
      setLoading(false);
      return () => {};
    }

    setLoading(true);
    if (debounceTimeout.current) {
      clearTimeout(debounceTimeout.current);
    }

    debounceTimeout.current = setTimeout(async () => {
      if (!connection) {
        setLoading(false);
        return;
      }
      try {
        const response = await renderTemplate(connection, template);
        setResult(response);
        setError(null);
      } catch (e: any) {
        setError(e?.message || "Failed to render template");
        setResult("");
      } finally {
        setLoading(false);
      }
    }, delay);

    return () => {
      if (debounceTimeout.current) {
        clearTimeout(debounceTimeout.current);
      }
    };
  }, [template, connection, delay]);

  const clear = useCallback(() => {
    setResult("");
    setError(null);
  }, []);

  return { result, error, loading, renderNow, clear };
}
