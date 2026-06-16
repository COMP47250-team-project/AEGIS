/**
 * Fixed-capacity circular (ring) buffer.
 * When full, the oldest item is overwritten by the newest.
 */
export class CircularBuffer<T> {
  private readonly buffer: Array<T | undefined>;
  private head = 0; // points to oldest item
  private tail = 0; // points to next write slot
  private count = 0;

  constructor(private readonly capacity: number = 500) {
    this.buffer = new Array<T | undefined>(capacity).fill(undefined);
  }

  /** Add an item. If full, the oldest item is silently dropped. */
  push(item: T): void {
    this.buffer[this.tail] = item;
    this.tail = (this.tail + 1) % this.capacity;

    if (this.count === this.capacity) {
      // Overwrite oldest — advance head
      this.head = (this.head + 1) % this.capacity;
    } else {
      this.count++;
    }
  }

  /** Remove and return the oldest item, or undefined if empty. */
  shift(): T | undefined {
    if (this.count === 0) return undefined;

    const item = this.buffer[this.head];
    this.buffer[this.head] = undefined;
    this.head = (this.head + 1) % this.capacity;
    this.count--;
    return item;
  }

  /** Drain all items oldest-first and return them as an array. */
  flush(): T[] {
    const items: T[] = [];
    let item = this.shift();
    while (item !== undefined) {
      items.push(item);
      item = this.shift();
    }
    return items;
  }

  /** Current number of items in the buffer. */
  get size(): number {
    return this.count;
  }

  /** True when no items are stored. */
  get isEmpty(): boolean {
    return this.count === 0;
  }

  /** True when the buffer has reached capacity. */
  get isFull(): boolean {
    return this.count === this.capacity;
  }
}