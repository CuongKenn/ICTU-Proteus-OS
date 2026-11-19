// Copyright (c) 2026 CuongKenn & ICTU Team
// SPDX-License-Identifier: AGPL-3.0-or-later

"use client";

import React from "react";
import { clsx } from "clsx";
import { Search } from "lucide-react";

export interface CategoryFilterProps {
  categories: string[];
  selectedCategory: string;
  onSelectCategory: (category: string) => void;
  searchQuery: string;
  onSearchChange: (query: string) => void;
}

export const CategoryFilter: React.FC<CategoryFilterProps> = ({
  categories,
  selectedCategory,
  onSelectCategory,
  searchQuery,
  onSearchChange,
}) => {
  return (
    <div className="flex flex-col md:flex-row md:items-center justify-between gap-3.5 w-full">
      {/* Category Pills */}
      <div className="flex items-center gap-1.5 overflow-x-auto pb-1 md:pb-0 scrollbar-hide shrink-0">
        {["All", ...categories].map((category) => {
          const isSelected = selectedCategory === category;
          const label = category === "All" ? "Tất cả" : category;
          return (
            <button
              key={category}
              type="button"
              onClick={() => onSelectCategory(category)}
              className={clsx(
                "px-3 py-1.5 rounded-lg text-[13px] font-medium whitespace-nowrap transition-colors cursor-pointer border",
                isSelected
                  ? "bg-ink text-paper-white border-transparent"
                  : "bg-paper-white text-muted border-line hover:text-ink hover:bg-paper-subtle hover:border-line-hi"
              )}
            >
              {label}
            </button>
          );
        })}
      </div>

      {/* Search */}
      <div className="relative w-full md:w-72 shrink-0">
        <Search className="h-4 w-4 text-dim absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none" />
        <input
          type="text"
          placeholder="Tìm kiếm ứng dụng..."
          value={searchQuery}
          onChange={(e) => onSearchChange(e.target.value)}
          className="input-field input-field-icon text-sm"
        />
      </div>
    </div>
  );
};
