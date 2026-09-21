<?php

/**
 * The invoice sender.
 *
 * Sends invoices to customers when they are due.
 */
class InvoiceSender
{
    // ============================================================
    // Handlers
    // ============================================================

    /** @param list<int> $ids */
    public function send(array $ids): void
    {
        // loop over the ids
        foreach ($ids as $id) {
            // $legacy = $this->oldSender->send($id);
            $this->dispatch($id);
        }

        // TODO: batch these
    }
}
