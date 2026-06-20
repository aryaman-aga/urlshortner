import { useRef, useEffect, useCallback, useState } from "react";
import { Button } from "@/components/ui/button";
import {
  Drawer,
  DrawerContent,
  DrawerTrigger,
  DrawerClose,
} from "@/components/ui/drawer";
import { Calendar } from "lucide-react";

interface IOSDatePickerProps {
  value: string;
  onChange: (value: string) => void;
}

const months = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];

const ITEM_HEIGHT = 40;
const VISIBLE_ITEMS = 5;

function getYears() {
  const now = new Date().getFullYear();
  return Array.from({ length: 6 }, (_, i) => now + i);
}

function getDaysInMonth(month: number, year: number) {
  return new Date(year, month + 1, 0).getDate();
}

function getHours() {
  return Array.from({ length: 24 }, (_, i) => i);
}

function getMinutes() {
  return Array.from({ length: 12 }, (_, i) => i * 5);
}

function padZero(n: number) {
  return n.toString().padStart(2, "0");
}

interface WheelColumnProps {
  items: { label: string; value: number }[];
  selected: number;
  onSelect: (value: number) => void;
}

const WheelColumn = ({ items, selected, onSelect }: WheelColumnProps) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const isScrollingRef = useRef(false);
  const timeoutRef = useRef<ReturnType<typeof setTimeout>>();

  const selectedIndex = items.findIndex((item) => item.value === selected);

  useEffect(() => {
    if (containerRef.current && !isScrollingRef.current) {
      const idx = items.findIndex((item) => item.value === selected);
      containerRef.current.scrollTop = idx * ITEM_HEIGHT;
    }
  }, [selected, items]);

  const handleScroll = useCallback(() => {
    isScrollingRef.current = true;
    if (timeoutRef.current) clearTimeout(timeoutRef.current);
    timeoutRef.current = setTimeout(() => {
      if (!containerRef.current) return;
      const scrollTop = containerRef.current.scrollTop;
      const index = Math.round(scrollTop / ITEM_HEIGHT);
      const clamped = Math.max(0, Math.min(index, items.length - 1));
      containerRef.current.scrollTo({ top: clamped * ITEM_HEIGHT, behavior: "smooth" });
      onSelect(items[clamped].value);
      isScrollingRef.current = false;
    }, 80);
  }, [items, onSelect]);

  const padding = Math.floor(VISIBLE_ITEMS / 2) * ITEM_HEIGHT;

  return (
    <div className="relative h-[200px] overflow-hidden flex-1">
      {/* Selection highlight */}
      <div
        className="absolute left-0 right-0 pointer-events-none z-10 border-y border-border bg-accent/50 rounded"
        style={{ top: padding, height: ITEM_HEIGHT }}
      />
      {/* Fade edges */}
      <div className="absolute inset-x-0 top-0 h-16 bg-gradient-to-b from-card to-transparent z-20 pointer-events-none" />
      <div className="absolute inset-x-0 bottom-0 h-16 bg-gradient-to-t from-card to-transparent z-20 pointer-events-none" />

      <div
        ref={containerRef}
        onScroll={handleScroll}
        className="h-full overflow-y-auto scrollbar-hide snap-y snap-mandatory"
        style={{
          paddingTop: padding,
          paddingBottom: padding,
          scrollbarWidth: "none",
          msOverflowStyle: "none",
        }}
      >
        {items.map((item, i) => (
          <div
            key={`${item.value}-${i}`}
            className={`flex items-center justify-center snap-center cursor-pointer transition-all duration-150 ${
              item.value === selected
                ? "text-foreground font-semibold text-base"
                : "text-muted-foreground text-sm opacity-60"
            }`}
            style={{ height: ITEM_HEIGHT }}
            onClick={() => {
              onSelect(item.value);
              containerRef.current?.scrollTo({ top: i * ITEM_HEIGHT, behavior: "smooth" });
            }}
          >
            {item.label}
          </div>
        ))}
      </div>
    </div>
  );
};

const IOSDatePicker = ({ value, onChange }: IOSDatePickerProps) => {
  const now = new Date();
  const initial = value ? new Date(value) : new Date(Date.now() + 86400000);

  const [month, setMonth] = useState(initial.getMonth());
  const [day, setDay] = useState(initial.getDate());
  const [year, setYear] = useState(initial.getFullYear());
  const [hour, setHour] = useState(initial.getHours());
  const [minute, setMinute] = useState(Math.floor(initial.getMinutes() / 5) * 5);
  const [open, setOpen] = useState(false);

  const years = getYears();
  const daysCount = getDaysInMonth(month, year);
  const days = Array.from({ length: daysCount }, (_, i) => i + 1);

  useEffect(() => {
    if (day > daysCount) setDay(daysCount);
  }, [month, year, daysCount, day]);

  const handleConfirm = () => {
    const d = new Date(year, month, day, hour, minute);
    onChange(d.toISOString().slice(0, 16));
    setOpen(false);
  };

  const displayValue = value
    ? `${months[month]} ${day}, ${year} ${padZero(hour)}:${padZero(minute)}`
    : "";

  return (
    <Drawer open={open} onOpenChange={setOpen}>
      <DrawerTrigger asChild>
        <button
          type="button"
          className="flex items-center w-full h-10 rounded-md border border-input bg-background px-3 text-sm ring-offset-background transition-colors hover:bg-accent/50 mt-1"
        >
          <Calendar className="h-4 w-4 mr-2 text-muted-foreground" />
          <span className={displayValue ? "text-foreground" : "text-muted-foreground"}>
            {displayValue || "Set expiry date"}
          </span>
        </button>
      </DrawerTrigger>
      <DrawerContent className="pb-6">
        <div className="mx-auto w-full max-w-sm px-4 pt-4">
          <p className="text-sm font-medium text-center text-muted-foreground mb-4">Select expiry date & time</p>

          <div className="flex gap-1 bg-card rounded-xl p-2">
            <WheelColumn
              items={months.map((m, i) => ({ label: m, value: i }))}
              selected={month}
              onSelect={setMonth}
            />
            <WheelColumn
              items={days.map((d) => ({ label: d.toString(), value: d }))}
              selected={day}
              onSelect={setDay}
            />
            <WheelColumn
              items={years.map((y) => ({ label: y.toString(), value: y }))}
              selected={year}
              onSelect={setYear}
            />
            <WheelColumn
              items={getHours().map((h) => ({ label: padZero(h), value: h }))}
              selected={hour}
              onSelect={setHour}
            />
            <WheelColumn
              items={getMinutes().map((m) => ({ label: padZero(m), value: m }))}
              selected={minute}
              onSelect={setMinute}
            />
          </div>

          <div className="flex gap-3 mt-5">
            <DrawerClose asChild>
              <Button variant="outline" className="flex-1">Cancel</Button>
            </DrawerClose>
            <Button className="flex-1" onClick={handleConfirm}>Confirm</Button>
          </div>
        </div>
      </DrawerContent>
    </Drawer>
  );
};

export default IOSDatePicker;
