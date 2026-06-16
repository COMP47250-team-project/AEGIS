import { CircularBuffer } from "../CircularBuffer";

describe("CircularBuffer", () => {
  it("starts empty", () => {
    const buf = new CircularBuffer<number>(3);
    expect(buf.size).toBe(0);
    expect(buf.isEmpty).toBe(true);
    expect(buf.isFull).toBe(false);
  });

  it("push and shift single item", () => {
    const buf = new CircularBuffer<number>(3);
    buf.push(1);
    expect(buf.size).toBe(1);
    expect(buf.shift()).toBe(1);
    expect(buf.size).toBe(0);
  });

  it("shift returns undefined when empty", () => {
    const buf = new CircularBuffer<number>(3);
    expect(buf.shift()).toBeUndefined();
  });

  it("maintains FIFO order", () => {
    const buf = new CircularBuffer<number>(3);
    buf.push(1);
    buf.push(2);
    buf.push(3);
    expect(buf.shift()).toBe(1);
    expect(buf.shift()).toBe(2);
    expect(buf.shift()).toBe(3);
  });

  it("reports full correctly", () => {
    const buf = new CircularBuffer<number>(3);
    buf.push(1);
    buf.push(2);
    buf.push(3);
    expect(buf.isFull).toBe(true);
  });

  it("overwrites oldest when full", () => {
    const buf = new CircularBuffer<number>(3);
    buf.push(1);
    buf.push(2);
    buf.push(3);
    buf.push(4); // overwrites 1
    expect(buf.size).toBe(3);
    expect(buf.shift()).toBe(2);
    expect(buf.shift()).toBe(3);
    expect(buf.shift()).toBe(4);
  });

  it("flush returns all items in order", () => {
    const buf = new CircularBuffer<number>(3);
    buf.push(1);
    buf.push(2);
    buf.push(3);
    expect(buf.flush()).toEqual([1, 2, 3]);
    expect(buf.isEmpty).toBe(true);
  });

  it("flush returns empty array when empty", () => {
    const buf = new CircularBuffer<number>(3);
    expect(buf.flush()).toEqual([]);
  });

  it("handles capacity of 1", () => {
    const buf = new CircularBuffer<number>(1);
    buf.push(1);
    buf.push(2); // overwrites 1
    expect(buf.shift()).toBe(2);
  });

  it("defaults to capacity 500", () => {
    const buf = new CircularBuffer<number>();
    for (let i = 0; i < 500; i++) buf.push(i);
    expect(buf.isFull).toBe(true);
    buf.push(500); // should overwrite 0
    expect(buf.shift()).toBe(1);
  });
});