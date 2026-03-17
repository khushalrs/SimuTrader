"use client";

import React, { useState, useEffect, useRef, ReactNode } from "react";

interface LazyLoadWrapperProps {
    children: ReactNode;
    active: boolean;
}

/**
 * A wrapper to defer rendering of its children until the `active` prop is true.
 * Once activated, it stays rendered to preserve state.
 */
export function LazyLoadWrapper({ children, active }: LazyLoadWrapperProps) {
    const [hasRendered, setHasRendered] = useState(false);
    
    useEffect(() => {
        if (active && !hasRendered) {
            setHasRendered(true);
        }
    }, [active, hasRendered]);

    if (!hasRendered && !active) {
        return null;
    }

    return <>{children}</>;
}
